"""CRM integrity review; GET-only and protected by the existing CRM boundary."""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request

from app.domain.crm.integrity import RULES, check_integrity
from app.integration.artifacts.storage import utcnow
from app.portal.routes import DbSession, templates

router = APIRouter()


@router.get("/crm/integrity", include_in_schema=False)
def integrity(
    request: Request,
    session: DbSession,
    year: int = Query(datetime.now(UTC).year - 1, ge=1900, le=9999),
    rule: str = "",
    severity: Literal["", "Error", "Review"] = "",
    kind: Literal["", "MAH", "Contact", "Self-declaration"] = "",
):
    if rule and rule not in RULES:
        raise HTTPException(422, "Select a known integrity check.")
    result = check_integrity(session, year)
    all_findings = result["findings"]
    rows = [
        f
        for f in all_findings
        if (not rule or f["rule"] == rule)
        and (not severity or f["severity"] == severity)
        and (not kind or f["kind"] == kind)
    ]
    return templates.TemplateResponse(
        request=request,
        name="crm_integrity.html",
        context={
            "title": "CRM · Data integrity",
            "active": "crm",
            "crm_section": True,
            "rows": rows,
            "rules": RULES,
            "rule": rule,
            "severity": severity,
            "kind": kind,
            "year": year,
            "checked_at": utcnow(),
            "current_mahs": result["current_mahs"],
            "eligible_mahs": result["eligible_mahs"],
            "error_count": sum(f["severity"] == "Error" for f in all_findings),
            "review_count": sum(f["severity"] == "Review" for f in all_findings),
            "affected_count": len({(f["kind"], f["id"]) for f in all_findings}),
        },
    )
