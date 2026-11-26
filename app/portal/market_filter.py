"""Canonical OR selection for requesting markets; empty selection retains all."""

from fastapi import HTTPException


def selected_markets(value):
    entries = [value] if isinstance(value, str) else value
    if (
        not isinstance(entries, (list, tuple))
        or len(entries) > 64
        or any(not isinstance(v, str) for v in entries)
    ):
        raise HTTPException(422, "Select up to 64 requesting markets.")
    if sum(len(v) for v in entries) > 1500:
        raise HTTPException(422, "The requesting market selection is too long.")
    result = list(
        dict.fromkeys(
            part.strip()
            for entry in entries
            for part in entry.split(",")
            if part.strip()
        )
    )
    if (
        len(result) > 64
        or any(len(v) > 100 for v in result)
        or not result
        and any(entry.strip() for entry in entries)
    ):
        raise HTTPException(422, "Select valid requesting markets.")
    return result
