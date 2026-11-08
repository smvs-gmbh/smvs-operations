"""Translate a question into allowlisted Exceptions directory filters."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.integration.openai.responses import structured_response


class ExceptionFilters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    supported: bool
    error: str
    market: str
    work_status: Literal["open", "resolved", "all"]
    days: int
    q: str


def interpret_filters(question, settings):
    draft = structured_response(
        settings,
        "Translate the question into read-only filters for the Exceptions directory. "
        "Supported filters: one alert code (A followed by digits, or empty), "
        "one requesting market (uppercase two or three letters, or empty), "
        "work status (open, resolved, or all; default all), "
        "last N UTC calendar days including today (1 to 367, default 30), "
        "and a single exact identifier search term (Alert ID, product code, batch, serial or transaction ID; "
        "use empty if absent). The directory runs a substring search for q. "
        "Set supported=false for unsupported dates, alternatives, aggregations, requested writes, "
        "or any predicate that the filters cannot express. Never silently discard a condition.",
        question,
        ExceptionFilters,
    )
    if not draft.supported:
        return None
    if (
        not 1 <= draft.days <= 367
        or (draft.error and not re.fullmatch(r"A[0-9]{1,4}", draft.error))
        or (draft.market and not re.fullmatch(r"[A-Z]{2,3}", draft.market))
        or len(draft.q) > 150
    ):
        raise ValueError("Unsupported search filters.")
    return draft
