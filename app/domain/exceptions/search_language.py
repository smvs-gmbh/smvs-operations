"""Translate a search question into a bounded draft of local filters."""

import httpx
from pydantic import BaseModel, ConfigDict

from app.domain.exceptions.repeat_evidence import OPERATIONS


class SearchDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    supported: bool
    operation: str
    market: str
    days: int
    matched_only: bool


def interpret(question, settings):
    response = httpx.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": "Bearer " + settings.openai_api_key.get_secret_value()
        },
        json={
            "model": settings.openai_search_model,
            "store": False,
            "instructions": (
                "Translate the user's question into filters for a read-only A7 repeat-operation preview. "
                "Supported filters are operation (EXPORTED, DESTROYED, or empty), "
                "requesting market (uppercase two or three letter code, or empty), "
                "and last N UTC calendar days (1 to 367, default 30). "
                "Use matched_only=true if the user asks for proven same-location repeats, "
                "otherwise false. Set supported=false for unsupported predicates such as batch, "
                "location ID, minimum repetition count, absolute dates or other alert codes. "
                "Never silently discard a condition. Do not perform or propose a write."
            ),
            "input": question,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "alert_search",
                    "strict": True,
                    "schema": SearchDraft.model_json_schema(),
                }
            },
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "completed":
        raise ValueError("Search interpretation was not completed.")
    output = [
        item["text"]
        for message in payload.get("output", [])
        if message.get("type") == "message"
        for item in message.get("content", [])
        if item.get("type") == "output_text"
    ]
    if len(output) != 1:
        raise ValueError("No search interpretation was returned.")
    draft = SearchDraft.model_validate_json(output[0])
    if not draft.supported:
        return None
    if (
        draft.operation and draft.operation not in OPERATIONS
    ) or not 1 <= draft.days <= 367:
        raise ValueError("Unsupported search filters.")
    if draft.market and (
        not draft.market.isascii()
        or not draft.market.isalpha()
        or not draft.market.isupper()
        or len(draft.market) not in (2, 3)
    ):
        raise ValueError("Unsupported market filter.")
    return draft
