"""Shared logo display policy. Original imported metadata is never rewritten."""

import re
from urllib.parse import urlsplit

from sqlalchemy import select

from app.core.db.models import StagingRow
from app.domain.crm.mah_profile import logo_url


def organisation_logo(source, profile, key, *, size=48):
    source = source or {}
    profile = profile or {}
    derived = logo_url(
        (profile.get("domain", source.get("Domain", "")) or ""), key, size=size
    )
    if derived:
        return derived
    for header in ("Logo URL", "Logo"):
        raw = source.get(header) or ""
        if not isinstance(raw, str):
            continue
        matches = (
            [raw.strip()]
            if raw.strip().startswith("https://")
            else re.findall(r"\((https://[^\s()]+)\)", raw)
        )
        for candidate in matches:
            try:
                parts = urlsplit(candidate)
            except ValueError:
                continue
            if (
                parts.scheme == "https"
                and parts.hostname
                and not parts.username
                and not parts.password
                and not any(c.isspace() for c in candidate)
            ):
                return candidate
    return None


def record_logos(session, records, key):
    source_ids = {
        row.source_row_id
        for row in records
        if not isinstance(row, StagingRow) and row.source_row_id
    }
    sources = (
        dict(
            session.execute(
                select(StagingRow.id, StagingRow.raw_row_json).where(
                    StagingRow.id.in_(source_ids)
                )
            ).all()
        )
        if source_ids
        else {}
    )
    return {
        row.id: organisation_logo(
            row.raw_row_json
            if isinstance(row, StagingRow)
            else sources.get(row.source_row_id) or {},
            getattr(row, "profile", None),
            key,
        )
        for row in records
    }
