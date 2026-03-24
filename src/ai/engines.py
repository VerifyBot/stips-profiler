"""
AI Engines — two processing strategies for building user profiles.

1. PromptCachingEngine  — For users with < 300 responses.
   Loads all text into context, makes 4 parallel calls (one per trunk).
   Leverages OpenAI's automatic prompt caching for cheap re-queries.

2. EmbeddingsEngine — For users with > 300 responses.
   Embeds all responses, uses semantic search to find relevant answers
   per category, then sends only those to the LLM.

Both engines return a validated UserProfileTree (Pydantic model).
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import numpy as np
from openai import OpenAI
from pydantic import BaseModel, Field

from src.ai.embeddings import generate_embeddings, multi_query_search
from src.ai.prompts import (
    CATEGORY_QUERIES,
    CATEGORY_SEARCH_QUERIES,
    SYSTEM_PROMPT_EXTRACTION,
    SYSTEM_PROMPT_SUMMARY,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model name constant
# ---------------------------------------------------------------------------
LLM_MODEL = "gpt-5.4-nano"
EMBEDDING_MODEL = "text-embedding-3-small"


# ---------------------------------------------------------------------------
# Pydantic models for structured output
# ---------------------------------------------------------------------------
class ExtractedFact(BaseModel):
    """A single fact extracted from the user's Stips answers."""
    fact: str
    source_quote: str  # Original Hebrew text as evidence
    question_id: Optional[int] = None  # Stips question ID for linking
    answer_date: Optional[str] = None  # Date of the answer (YYYY-MM-DD)
    importance: int = Field(default=5, ge=1, le=10)  # 1-10 importance score


class DynamicCategory(BaseModel):
    """A dynamically-named sub-category containing related facts."""
    category_name: str  # e.g. "Bagrut Struggles", "K-Pop Obsession"
    facts: list[ExtractedFact]


class CategoryResult(BaseModel):
    """Result for a single top-level category extraction."""
    categories: list[DynamicCategory]


class UserProfileTree(BaseModel):
    """
    The complete user profile tree with 4 fixed trunks.
    Each trunk contains dynamic sub-categories invented by the LLM.
    """
    personal_and_demographic: list[DynamicCategory]
    education_and_career: list[DynamicCategory]
    social_and_family: list[DynamicCategory]
    interests_and_beliefs: list[DynamicCategory]

    def total_facts(self) -> int:
        """Count total extracted facts across all categories."""
        count = 0
        for trunk in [
            self.personal_and_demographic,
            self.education_and_career,
            self.social_and_family,
            self.interests_and_beliefs,
        ]:
            for cat in trunk:
                count += len(cat.facts)
        return count

    def to_display_dict(self) -> dict[str, Any]:
        """Convert to a nested dict for the TUI dashboard.
        
        Facts within each sub-category are sorted by a composite score:
            importance * 0.6 + recency * 0.4
        where recency is normalized from 0 (oldest) to 10 (most recent).
        """
        result: dict[str, Any] = {}
        trunk_map = {
            "👤 Personal & Demographic": self.personal_and_demographic,
            "🎓 Education & Career": self.education_and_career,
            "👨‍👩‍👧 Social & Family": self.social_and_family,
            "🎸 Interests & Beliefs": self.interests_and_beliefs,
        }

        # Collect all dates across all facts to compute recency
        all_dates: list[datetime] = []
        for categories in trunk_map.values():
            for cat in categories:
                for f in cat.facts:
                    if f.answer_date:
                        try:
                            all_dates.append(datetime.strptime(f.answer_date, "%Y-%m-%d"))
                        except ValueError:
                            pass

        # Compute date range for normalization
        now = datetime.now()
        oldest = min(all_dates) if all_dates else now - timedelta(days=365)
        date_range_days = max((now - oldest).days, 1)

        def _sort_key(f: ExtractedFact) -> float:
            importance = f.importance or 5
            recency = 5.0  # default middle
            if f.answer_date:
                try:
                    d = datetime.strptime(f.answer_date, "%Y-%m-%d")
                    days_ago = (now - d).days
                    recency = max(0, 10 * (1 - days_ago / date_range_days))
                except ValueError:
                    pass
            return importance * 0.6 + recency * 0.4

        for label, categories in trunk_map.items():
            result[label] = {}
            for cat in categories:
                # Sort facts by composite score (highest first)
                sorted_facts = sorted(cat.facts, key=_sort_key, reverse=True)
                facts_list = [
                    {
                        "fact": f.fact,
                        "source_quote": f.source_quote,
                        "question_id": f.question_id,
                        "answer_date": f.answer_date,
                        "importance": f.importance,
                    }
                    for f in sorted_facts
                ]
                result[label][f"{cat.category_name} ({len(cat.facts)} facts)"] = facts_list
        return result

    def to_serializable_dict(self) -> dict[str, Any]:
        """Convert to a JSON-serializable dict for caching."""
        return self.model_dump()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _format_qa_pairs(responses: list[dict[str, Any]]) -> str:
    """Format response dicts into a readable Q&A block for the LLM.
    
    Includes QuestionID and Date metadata for the LLM to echo back.
    """
    lines: list[str] = []
    for i, resp in enumerate(responses, 1):
        q = resp.get("question", resp.get("question_text", ""))
        a = resp.get("answer", resp.get("answer_text", ""))
        t = resp.get("time", resp.get("answer_time", ""))
        qid = resp.get("question_id")

        # Extract date from time field (format: "YYYY/MM/DD HH:MM:SS")
        date_str = ""
        if t:
            try:
                date_str = t.split(" ")[0].replace("/", "-")
            except (IndexError, AttributeError):
                date_str = ""

        # Add metadata tags for the LLM to echo back
        meta_parts = []
        if qid:
            meta_parts.append(f"[QuestionID: {qid}]")
        if date_str:
            meta_parts.append(f"[Date: {date_str}]")
        meta_line = " ".join(meta_parts)

        if meta_line:
            lines.append(f"[{i}] {meta_line}")
        else:
            lines.append(f"[{i}]")
        lines.append(f"Q: {q}")
        lines.append(f"A: {a}")
        lines.append("")
    return "\n".join(lines)


def _extract_single_category(
    client: OpenAI,
    trunk_key: str,
    qa_block: str,
) -> list[DynamicCategory]:
    """
    Run a single structured-output extraction for one category trunk.
    Returns a list of DynamicCategory objects.
    """
    category_instruction = CATEGORY_QUERIES[trunk_key]

    try:
        completion = client.beta.chat.completions.parse(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_EXTRACTION},
                {"role": "user", "content": qa_block},
                {"role": "user", "content": category_instruction},
            ],
            response_format=CategoryResult,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            logger.warning("LLM returned None for trunk '%s'", trunk_key)
            return []
        return parsed.categories
    except Exception as exc:
        logger.error("LLM extraction failed for '%s': %s", trunk_key, exc)
        return []


# ---------------------------------------------------------------------------
# Engine 1: Prompt Caching (< 300 responses)
# ---------------------------------------------------------------------------
class PromptCachingEngine:
    """
    Loads all user responses into the LLM context and makes 4 parallel
    extraction calls (one per category trunk).  Takes advantage of OpenAI's
    automatic prompt caching — the system prompt + Q&A data prefix is
    identical across all 4 calls, so it's cached after the first.
    """

    def __init__(self, client: OpenAI) -> None:
        self._client = client

    async def extract(
        self,
        responses: list[dict[str, Any]],
        on_category_done: Optional[object] = None,
    ) -> UserProfileTree:
        """
        Run parallel extraction for all 4 category trunks.

        Args:
            responses:         List of parsed response dicts.
            on_category_done:  Optional callback(trunk_key) called when a
                               category finishes extraction.
        """
        qa_block = _format_qa_pairs(responses)
        trunk_keys = list(CATEGORY_QUERIES.keys())

        # Run extractions in parallel using threads (OpenAI SDK is sync)
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(
                None, _extract_single_category, self._client, key, qa_block
            )
            for key in trunk_keys
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        profile_data: dict[str, list[DynamicCategory]] = {}
        for key, result in zip(trunk_keys, results):
            if isinstance(result, Exception):
                logger.error("Extraction failed for '%s': %s", key, result)
                profile_data[key] = []
            else:
                profile_data[key] = result

            if on_category_done is not None:
                on_category_done(key)  # type: ignore[operator]

        return UserProfileTree(**profile_data)


# ---------------------------------------------------------------------------
# Engine 2: Embeddings + RAG (> 300 responses)
# ---------------------------------------------------------------------------
class EmbeddingsEngine:
    """
    For large-volume users.  Embeds all responses, performs semantic search
    to find the most relevant answers per category, then sends only those
    to the LLM for extraction.
    """

    def __init__(
        self,
        client: OpenAI,
        top_k_per_category: int = 50,
    ) -> None:
        self._client = client
        self._top_k = top_k_per_category

    async def extract(
        self,
        responses: list[dict[str, Any]],
        cached_embeddings: Optional[tuple[list[int], np.ndarray]] = None,
        on_embeddings_done: Optional[object] = None,
        on_category_done: Optional[object] = None,
    ) -> tuple[UserProfileTree, tuple[list[int], np.ndarray]]:
        """
        Run the full RAG pipeline: embed → search → extract.

        Args:
            responses:          List of parsed response dicts.
            cached_embeddings:  Optional (answer_ids, matrix) from cache.
            on_embeddings_done: Optional callback() when embedding is complete.
            on_category_done:   Optional callback(trunk_key).

        Returns:
            (UserProfileTree, (answer_ids, embeddings_matrix))
            — the second element should be cached for future runs.
        """
        # Build text corpus: "Q: ... A: ..." for each response
        answer_ids: list[int] = []
        texts: list[str] = []
        for resp in responses:
            q = resp.get("question", resp.get("question_text", ""))
            a = resp.get("answer", resp.get("answer_text", ""))
            answer_ids.append(resp.get("answer_id", 0))
            texts.append(f"Q: {q}\nA: {a}")

        # Step 1: Generate or load embeddings
        if cached_embeddings is not None:
            cached_ids, cached_matrix = cached_embeddings
            cached_id_set = set(cached_ids)

            # Find new responses that need embedding
            new_indices = [i for i, aid in enumerate(answer_ids) if aid not in cached_id_set]

            if new_indices:
                new_texts = [texts[i] for i in new_indices]
                new_embeddings = generate_embeddings(new_texts, self._client)

                # Merge
                new_ids = [answer_ids[i] for i in new_indices]
                all_ids = cached_ids + new_ids
                all_matrix = np.vstack([cached_matrix, new_embeddings])
            else:
                all_ids = cached_ids
                all_matrix = cached_matrix
        else:
            all_matrix = generate_embeddings(texts, self._client)
            all_ids = answer_ids

        if on_embeddings_done is not None:
            on_embeddings_done()  # type: ignore[operator]

        # Build a lookup from answer_id to response dict
        resp_by_id: dict[int, dict[str, Any]] = {}
        for resp in responses:
            resp_by_id[resp.get("answer_id", 0)] = resp

        # Step 2: Per-category semantic search + LLM extraction
        trunk_keys = list(CATEGORY_QUERIES.keys())
        loop = asyncio.get_event_loop()

        async def _process_trunk(trunk_key: str) -> list[DynamicCategory]:
            # Embed the category seed queries
            seed_queries = CATEGORY_SEARCH_QUERIES.get(trunk_key, [])
            if not seed_queries:
                return []

            query_embeddings = await loop.run_in_executor(
                None, generate_embeddings, seed_queries, self._client
            )

            # Semantic search
            relevant_indices = multi_query_search(
                query_embeddings, all_matrix, top_k_per_query=self._top_k
            )

            # Map indices back to answer_ids, then to response dicts
            relevant_responses = []
            for idx in relevant_indices:
                if idx < len(all_ids):
                    aid = all_ids[idx]
                    if aid in resp_by_id:
                        relevant_responses.append(resp_by_id[aid])

            if not relevant_responses:
                return []

            # LLM extraction on the filtered subset
            qa_block = _format_qa_pairs(relevant_responses)
            result = await loop.run_in_executor(
                None, _extract_single_category, self._client, trunk_key, qa_block
            )

            if on_category_done is not None:
                on_category_done(trunk_key)  # type: ignore[operator]

            return result if not isinstance(result, Exception) else []

        trunk_results = await asyncio.gather(
            *[_process_trunk(key) for key in trunk_keys],
            return_exceptions=True,
        )

        profile_data: dict[str, list[DynamicCategory]] = {}
        for key, result in zip(trunk_keys, trunk_results):
            if isinstance(result, Exception):
                logger.error("RAG extraction failed for '%s': %s", key, result)
                profile_data[key] = []
            else:
                profile_data[key] = result

        tree = UserProfileTree(**profile_data)
        return tree, (all_ids, all_matrix)


# ---------------------------------------------------------------------------
# Summary generation utility
# ---------------------------------------------------------------------------
def generate_category_summary(
    client: OpenAI,
    category_name: str,
    facts: list[ExtractedFact],
) -> str:
    """Generate a brief AI summary for a sub-category's facts."""
    facts_text = "\n".join(
        f"- {f.fact} (Source: \"{f.source_quote}\")" for f in facts
    )

    try:
        completion = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_SUMMARY},
                {
                    "role": "user",
                    "content": (
                        f"Category: {category_name}\n\n"
                        f"Extracted facts:\n{facts_text}\n\n"
                        "Write a 1-3 sentence psychological summary."
                    ),
                },
            ],
            max_tokens=200,
        )
        return completion.choices[0].message.content or "No summary available."
    except Exception as exc:
        logger.error("Summary generation failed: %s", exc)
        return "Summary generation failed."
