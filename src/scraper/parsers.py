"""
Parsers — pure functions that transform raw Stips API JSON into clean dicts.

These functions know nothing about HTTP, caching, or AI.
They simply normalise raw API responses into a consistent internal format.
"""

from typing import Any


def parse_user_meta(raw_profile: dict[str, Any], raw_omni: dict[str, Any]) -> dict[str, Any]:
    """
    Parse the raw profile.page_data and omniobj API responses into a clean user dict.

    Returns:
        {
            "user_id":      int,
            "nickname":     str,
            "flower_count": int,
            "age":          int | None,
            "text_status":  str | None,
        }

    Raises:
        ValueError: if the response doesn't contain valid user data.
    """
    status_prof = raw_profile.get("status")
    data_prof = raw_profile.get("data")

    if status_prof != "ok" or not data_prof or not isinstance(data_prof, dict):
        raise ValueError(f"Invalid API response: status={status_prof}, data is empty or malformed")

    # Extract nickname from OmniObj
    omni_data = raw_omni.get("data", {}).get("omniOmniObj", {}).get("data", {})
    nickname = omni_data.get("nickname")

    if not nickname:
        # Fallback just in case omni request failed or returned empty
        nickname = data_prof.get("nickname", "Unknown")

    flower_count = data_prof.get("flowers", 0)
    age = data_prof.get("age")
    
    profile_page = data_prof.get("user_profile_page", {})
    profile_data = profile_page.get("data", {}) if isinstance(profile_page, dict) else {}
    text_status = profile_data.get("text_status")

    return {
        "nickname": nickname,
        "flower_count": int(flower_count),
        "age": int(age) if age is not None else None,
        "text_status": text_status,
    }



def parse_answers(raw_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Parse a list of raw answer objects from the objectlist API endpoint.

    Each item in `raw_items` has the structure:
        { "objType": "ans", "data": {...}, "extra": {...}, "meta": {...} }

    Returns a list of dicts:
        {
            "answer_id":   int,
            "question_id": int | None,  # data.askid — the Stips question ID
            "question":    str,         # extra.parent_item_title
            "answer":      str,         # data.a
            "time":        str,         # data.time  (YYYY/MM/DD HH:MM:SS)
            "raw":         dict,        # full original object for future use
        }
    """
    parsed: list[dict[str, Any]] = []

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        item_data = item.get("data", {})
        item_extra = item.get("extra", {})

        answer_id = item_data.get("id")
        answer_text = item_data.get("a", "")
        answer_time = item_data.get("time", "")
        question_text = item_extra.get("parent_item_title", "")
        question_id = item_data.get("askid")

        if answer_id is None:
            continue  # Skip malformed entries

        parsed.append({
            "answer_id": int(answer_id),
            "question_id": int(question_id) if question_id is not None else None,
            "question": question_text,
            "answer": answer_text,
            "time": answer_time,
            "raw": item,
        })

    return parsed
