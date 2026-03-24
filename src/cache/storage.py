"""
Cache Layer — SQLite-backed local storage for Stips data and embeddings.

Tables:
  - users:      User metadata (nickname, flower count, profile JSON)
  - responses:  Individual Q&A pairs (answer text, question text, timestamps)
  - embeddings: Serialized numpy embedding vectors per answer
  - ai_results: Cached AI profile trees per engine type

The cache enforces isolation: each method operates on a specific user_id,
and all writes are transactional.
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DB_DIR = Path(__file__).resolve().parents[2] / ".cache"
_DB_PATH = _DB_DIR / "stips_cache.db"


class CacheStorage:
    """Thread-safe, file-based SQLite cache for Stips profiler data."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or _DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()
        self._migrate()

    # ------------------------------------------------------------------
    # Schema bootstrap
    # ------------------------------------------------------------------
    def _create_tables(self) -> None:
        with self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id       INTEGER PRIMARY KEY,
                    nickname      TEXT    NOT NULL,
                    flower_count  INTEGER NOT NULL DEFAULT 0,
                    raw_profile   TEXT,          -- full JSON from profile API
                    fetched_at    REAL   NOT NULL
                );

                CREATE TABLE IF NOT EXISTS responses (
                    answer_id     INTEGER PRIMARY KEY,
                    user_id       INTEGER NOT NULL,
                    question_id   INTEGER,
                    question_text TEXT    NOT NULL,
                    answer_text   TEXT    NOT NULL,
                    answer_time   TEXT,
                    raw_json      TEXT,
                    fetched_at    REAL   NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );

                CREATE INDEX IF NOT EXISTS idx_responses_user
                    ON responses(user_id);

                CREATE TABLE IF NOT EXISTS embeddings (
                    answer_id     INTEGER PRIMARY KEY,
                    user_id       INTEGER NOT NULL,
                    embedding     BLOB   NOT NULL,   -- numpy .tobytes()
                    model_name    TEXT   NOT NULL,
                    created_at    REAL   NOT NULL,
                    FOREIGN KEY (user_id)   REFERENCES users(user_id),
                    FOREIGN KEY (answer_id) REFERENCES responses(answer_id)
                );

                CREATE TABLE IF NOT EXISTS ai_results (
                    user_id       INTEGER NOT NULL,
                    engine_type   TEXT    NOT NULL,
                    profile_json  TEXT    NOT NULL,
                    created_at    REAL    NOT NULL,
                    PRIMARY KEY (user_id, engine_type),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );
            """)

    def _migrate(self) -> None:
        """Add columns that may be missing from older DB versions."""
        cursor = self._conn.execute("PRAGMA table_info(responses)")
        columns = {row["name"] for row in cursor.fetchall()}
        if "question_id" not in columns:
            with self._conn:
                self._conn.execute(
                    "ALTER TABLE responses ADD COLUMN question_id INTEGER"
                )

    # ------------------------------------------------------------------
    # User metadata
    # ------------------------------------------------------------------
    def get_user_meta(self, user_id: int) -> Optional[dict[str, Any]]:
        """Return cached user metadata or None."""
        row = self._conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def save_user_meta(
        self,
        user_id: int,
        nickname: str,
        flower_count: int,
        raw_profile: dict[str, Any],
    ) -> None:
        """Upsert user metadata."""
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO users (user_id, nickname, flower_count, raw_profile, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    nickname     = excluded.nickname,
                    flower_count = excluded.flower_count,
                    raw_profile  = excluded.raw_profile,
                    fetched_at   = excluded.fetched_at
                """,
                (user_id, nickname, flower_count, json.dumps(raw_profile, ensure_ascii=False), time.time()),
            )

    # ------------------------------------------------------------------
    # Responses
    # ------------------------------------------------------------------
    def get_responses(self, user_id: int) -> list[dict[str, Any]]:
        """Return all cached responses for a user, ordered newest-first."""
        rows = self._conn.execute(
            "SELECT * FROM responses WHERE user_id = ? ORDER BY answer_id DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_response_count(self, user_id: int) -> int:
        """Return the number of cached responses for a user."""
        row = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM responses WHERE user_id = ?", (user_id,)
        ).fetchone()
        return row["cnt"] if row else 0

    def get_max_answer_id(self, user_id: int) -> Optional[int]:
        """Return the highest cached answer_id for incremental fetching."""
        row = self._conn.execute(
            "SELECT MAX(answer_id) AS max_id FROM responses WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return row["max_id"] if row and row["max_id"] is not None else None

    def get_all_answer_ids(self, user_id: int) -> set[int]:
        """Return set of all cached answer IDs for a user."""
        rows = self._conn.execute(
            "SELECT answer_id FROM responses WHERE user_id = ?", (user_id,)
        ).fetchall()
        return {r["answer_id"] for r in rows}

    def save_responses(self, user_id: int, responses: list[dict[str, Any]]) -> int:
        """
        Bulk-insert responses (skips duplicates via INSERT OR IGNORE).
        Returns the number of newly inserted rows.
        """
        inserted = 0
        with self._conn:
            for resp in responses:
                cur = self._conn.execute(
                    """
                    INSERT OR IGNORE INTO responses
                        (answer_id, user_id, question_id, question_text, answer_text,
                         answer_time, raw_json, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        resp["answer_id"],
                        user_id,
                        resp.get("question_id"),
                        resp["question"],
                        resp["answer"],
                        resp.get("time", ""),
                        json.dumps(resp.get("raw", {}), ensure_ascii=False),
                        time.time(),
                    ),
                )
                inserted += cur.rowcount
        return inserted

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------
    def get_embeddings(
        self, user_id: int
    ) -> Optional[tuple[list[int], np.ndarray]]:
        """
        Return cached embeddings for a user.
        Returns (answer_ids, embeddings_matrix) or None if nothing cached.
        """
        rows = self._conn.execute(
            "SELECT answer_id, embedding FROM embeddings WHERE user_id = ? ORDER BY answer_id",
            (user_id,),
        ).fetchall()
        if not rows:
            return None

        answer_ids = [r["answer_id"] for r in rows]
        # Each embedding row is a float32 numpy array serialized via tobytes()
        vectors = [np.frombuffer(r["embedding"], dtype=np.float32) for r in rows]
        return answer_ids, np.vstack(vectors)

    def save_embeddings(
        self,
        user_id: int,
        answer_ids: list[int],
        embeddings: np.ndarray,
        model_name: str = "text-embedding-3-small",
    ) -> None:
        """Bulk-upsert embedding vectors for a set of answers."""
        now = time.time()
        with self._conn:
            for aid, vec in zip(answer_ids, embeddings):
                self._conn.execute(
                    """
                    INSERT INTO embeddings (answer_id, user_id, embedding, model_name, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(answer_id) DO UPDATE SET
                        embedding  = excluded.embedding,
                        model_name = excluded.model_name,
                        created_at = excluded.created_at
                    """,
                    (aid, user_id, vec.astype(np.float32).tobytes(), model_name, now),
                )

    def get_embedded_answer_ids(self, user_id: int) -> set[int]:
        """Return set of answer IDs that already have embeddings cached."""
        rows = self._conn.execute(
            "SELECT answer_id FROM embeddings WHERE user_id = ?", (user_id,)
        ).fetchall()
        return {r["answer_id"] for r in rows}

    # ------------------------------------------------------------------
    # AI Results caching
    # ------------------------------------------------------------------
    def get_ai_results(
        self, user_id: int, engine_type: str
    ) -> Optional[tuple[dict[str, Any], float]]:
        """
        Return cached AI profile results for a user+engine combination.
        Returns (profile_dict, created_at_timestamp) or None.
        """
        row = self._conn.execute(
            "SELECT profile_json, created_at FROM ai_results "
            "WHERE user_id = ? AND engine_type = ?",
            (user_id, engine_type),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["profile_json"]), row["created_at"]

    def save_ai_results(
        self, user_id: int, engine_type: str, profile_json: dict[str, Any]
    ) -> None:
        """Upsert AI profile results for a user+engine combination."""
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO ai_results (user_id, engine_type, profile_json, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, engine_type) DO UPDATE SET
                    profile_json = excluded.profile_json,
                    created_at   = excluded.created_at
                """,
                (user_id, engine_type, json.dumps(profile_json, ensure_ascii=False), time.time()),
            )

    def clear_ai_results(self, user_id: int) -> None:
        """Delete all cached AI results for a specific user."""
        with self._conn:
            self._conn.execute(
                "DELETE FROM ai_results WHERE user_id = ?", (user_id,)
            )

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------
    def clear_user_cache(self, user_id: int) -> None:
        """Delete ALL cached data for a specific user."""
        with self._conn:
            self._conn.execute("DELETE FROM ai_results WHERE user_id = ?", (user_id,))
            self._conn.execute("DELETE FROM embeddings WHERE user_id = ?", (user_id,))
            self._conn.execute("DELETE FROM responses WHERE user_id = ?", (user_id,))
            self._conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
