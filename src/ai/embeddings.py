"""
Embeddings — vector generation and semantic search utilities.

Uses OpenAI's text-embedding-3-small model and numpy for cosine similarity.
All heavy math is done in-memory with numpy for speed.
"""

import logging
from typing import Optional

import numpy as np
from openai import OpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_EMBEDDING_MODEL = "text-embedding-3-small"
_BATCH_SIZE = 512  # OpenAI allows up to 2048 inputs, but 512 is safer


def generate_embeddings(
    texts: list[str],
    client: OpenAI,
    model: str = _EMBEDDING_MODEL,
    on_progress: Optional[object] = None,
) -> np.ndarray:
    """
    Generate embeddings for a list of texts using OpenAI's API.

    Batches requests to stay within API limits.

    Args:
        texts:       List of strings to embed.
        client:      Initialised OpenAI client.
        model:       Embedding model name.
        on_progress: Optional callable(done, total) for progress reporting.

    Returns:
        numpy array of shape (len(texts), embedding_dim).
    """
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]

        # Filter out empty strings (API rejects them)
        batch = [t if t.strip() else " " for t in batch]

        try:
            response = client.embeddings.create(input=batch, model=model)
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)
        except Exception as exc:
            logger.error("Embedding API error on batch %d: %s", i // _BATCH_SIZE, exc)
            # Fill with zero vectors so indices stay aligned
            dim = len(all_embeddings[0]) if all_embeddings else 1536
            all_embeddings.extend([[0.0] * dim] * len(batch))

        if on_progress is not None:
            on_progress(min(i + _BATCH_SIZE, len(texts)), len(texts))  # type: ignore[operator]

    return np.array(all_embeddings, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Compute cosine similarity between vectors in `a` and vectors in `b`.

    Args:
        a: shape (m, d) or (d,)
        b: shape (n, d)

    Returns:
        shape (m, n) similarity matrix, or (n,) if a is 1-D.
    """
    if a.ndim == 1:
        a = a.reshape(1, -1)
        squeeze = True
    else:
        squeeze = False

    # Normalise
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-10)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)

    sim = a_norm @ b_norm.T

    return sim.squeeze(0) if squeeze else sim


def semantic_search(
    query_embedding: np.ndarray,
    corpus_embeddings: np.ndarray,
    top_k: int = 30,
) -> list[int]:
    """
    Find the top-k most similar corpus items to the query.

    Args:
        query_embedding:   shape (d,) — a single query vector.
        corpus_embeddings: shape (n, d) — all corpus vectors.
        top_k:             How many top results to return.

    Returns:
        List of indices into `corpus_embeddings`, sorted by descending similarity.
    """
    sims = cosine_similarity(query_embedding, corpus_embeddings)
    top_k = min(top_k, len(sims))
    top_indices = np.argsort(sims)[::-1][:top_k]
    return top_indices.tolist()


def multi_query_search(
    query_embeddings: np.ndarray,
    corpus_embeddings: np.ndarray,
    top_k_per_query: int = 20,
) -> list[int]:
    """
    Run semantic search with multiple query vectors and return the union
    of top results (deduplicated), ordered by max similarity score.

    Args:
        query_embeddings:  shape (q, d)
        corpus_embeddings: shape (n, d)
        top_k_per_query:   Top-k to retrieve per query.

    Returns:
        Deduplicated list of corpus indices, sorted by best score.
    """
    sim_matrix = cosine_similarity(query_embeddings, corpus_embeddings)  # (q, n)
    max_scores = sim_matrix.max(axis=0)  # (n,) — best score per corpus item

    # Take union of top-k per query
    candidate_set: set[int] = set()
    for q_idx in range(sim_matrix.shape[0]):
        row = sim_matrix[q_idx]
        top_k = min(top_k_per_query, len(row))
        top_indices = np.argsort(row)[::-1][:top_k]
        candidate_set.update(top_indices.tolist())

    # Sort candidates by their best score across all queries
    sorted_candidates = sorted(candidate_set, key=lambda i: max_scores[i], reverse=True)
    return sorted_candidates
