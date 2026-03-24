"""
Stips HTTP Client — async scraper for user metadata and flowered answers.

Uses httpx.AsyncClient with retry logic, proper browser-like headers,
and paginated fetching with incremental cache support (stops when it
encounters an already-cached answer ID).
"""

import asyncio
import json
import logging
from typing import Any, Optional

import httpx

from src.scraper.parsers import parse_answers, parse_user_meta

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_BASE_URL = "https://stips.co.il/api"
_DEFAULT_HEADERS: dict[str, str] = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "en-US,en;q=0.9,he;q=0.8",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "sec-ch-ua": '"Chromium";v="143", "Not-A.Brand";v="14", "Google Chrome";v="126"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/6.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.2 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/520.36"
    ),
}

_MAX_RETRIES = 3
_RETRY_BACKOFF = 1.5  # seconds, multiplied per attempt
_PAGE_DELAY = 0.3     # polite delay between paginated requests


class StipsClientError(Exception):
    """Raised on unrecoverable Stips API errors."""


class StipsClient:
    """Async HTTP client for the Stips.co.il API."""

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=_DEFAULT_HEADERS,
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Low-level request with retry
    # ------------------------------------------------------------------
    async def _request(
        self, params: dict[str, str], referer: str
    ) -> dict[str, Any]:
        """
        Make a GET request to the Stips API with automatic retries.

        Raises StipsClientError after exhausting retries.
        """
        client = await self._ensure_client()
        last_error: Optional[Exception] = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = await client.get(
                    _BASE_URL,
                    params=params,
                    headers={"referer": referer},
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("status") != "ok":
                    raise StipsClientError(
                        f"API returned non-ok status: {data.get('status')}, "
                        f"error_code: {data.get('error_code', 'N/A')}"
                    )
                return data

            except httpx.HTTPStatusError as exc:
                last_error = exc
                logger.warning(
                    "Stips API HTTP %s on attempt %d/%d",
                    exc.response.status_code, attempt, _MAX_RETRIES,
                )
            except (httpx.RequestError, json.JSONDecodeError) as exc:
                last_error = exc
                logger.warning(
                    "Stips API request error on attempt %d/%d: %s",
                    attempt, _MAX_RETRIES, exc,
                )

            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_BACKOFF * attempt)

        raise StipsClientError(
            f"Failed after {_MAX_RETRIES} retries: {last_error}"
        ) from last_error

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------
    async def fetch_user_meta(self, user_id: int) -> dict[str, Any]:
        """
        Fetch lightweight user metadata (nickname, flower count, etc.).
        Returns a parsed dict — see parsers.parse_user_meta for shape.
        """
        referer = f"https://stips.co.il/profile/{user_id}"
        
        # Profile page data (for flowers, age, status)
        profile_task = self._request(
            params={
                "name": "profile.page_data",
                "api_params": json.dumps({"userid": user_id}),
            },
            referer=referer,
        )
        
        # OmniObj data (for nickname)
        omni_task = self._request(
            params={
                "name": "omniobj",
                "rest_action": "GET",
                "omniobj": json.dumps({"objType": "user", "data": {"id": user_id}}),
            },
            referer=referer,
        )
        
        raw_profile, raw_omni = await asyncio.gather(profile_task, omni_task)
        
        meta = parse_user_meta(raw_profile, raw_omni)
        meta["user_id"] = user_id
        meta["_raw"] = {"profile": raw_profile, "omni": raw_omni}
        return meta

    async def fetch_flowered_answers(
        self,
        user_id: int,
        known_answer_ids: Optional[set[int]] = None,
        on_page_fetched: Any = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch ALL flowered answers for a user, paginating until the API
        returns an empty page.

        Incremental mode: if `known_answer_ids` is provided, the fetcher
        stops as soon as it encounters an answer ID that's already cached.
        This means we only download NEW answers.

        Args:
            user_id:           The Stips user ID.
            known_answer_ids:  Set of answer IDs already in the local cache.
            on_page_fetched:   Optional async callback(page_num, items_so_far)
                               for progress reporting.

        Returns:
            List of parsed answer dicts (see parsers.parse_answers).
        """
        known = known_answer_ids or set()
        all_answers: list[dict[str, Any]] = []
        page = 1
        hit_known = False

        referer = f"https://stips.co.il/profile/{user_id}"

        while True:
            try:
                raw = await self._request(
                    params={
                        "name": "objectlist",
                        "api_params": json.dumps({
                            "userid": user_id,
                            "method": "ans.flower_for_user",
                            "page": page,
                        }),
                    },
                    referer=referer,
                )
            except StipsClientError:
                logger.error("Failed to fetch page %d for user %d", page, user_id)
                break

            # The API returns either data as a direct list or data.items
            raw_data = raw.get("data", [])
            if isinstance(raw_data, dict):
                raw_items = raw_data.get("items", [])
            elif isinstance(raw_data, list):
                raw_items = raw_data
            else:
                raw_items = []

            if not raw_items:
                break  # No more pages

            parsed = parse_answers(raw_items)

            # Check for overlap with known IDs (incremental caching)
            new_answers: list[dict[str, Any]] = []
            for ans in parsed:
                if ans["answer_id"] in known:
                    hit_known = True
                    break
                new_answers.append(ans)

            all_answers.extend(new_answers)

            if on_page_fetched is not None:
                await on_page_fetched(page, len(all_answers))

            if hit_known:
                logger.info(
                    "Incremental fetch: hit known answer on page %d, stopping.",
                    page,
                )
                break

            page += 1
            await asyncio.sleep(_PAGE_DELAY)  # Be polite

        return all_answers
