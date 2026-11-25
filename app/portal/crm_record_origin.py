"""Explicit, tab-local return context for related CRM records."""

import re
from urllib.parse import parse_qsl, urlencode

from app.domain.models import (
    CRMAgreement,
    CRMContact,
    CRMEndUser,
    CRMMah,
    CRMSelfDeclaration,
)

MODELS = {
    "mahs": (CRMMah, "MAH", "name"),
    "end-users": (CRMEndUser, "End User", "name"),
    "contacts": (CRMContact, "Contact", "display_name"),
    "agreements": (CRMAgreement, "Agreement", "contract_id"),
    "self-declarations": (CRMSelfDeclaration, "Self-declaration", "record_label"),
}
# Only list/view context; never arbitrary destinations, editing commands or nested origins.
CONTEXT_KEYS = {
    "q",
    "agreement",
    "archived",
    "unlinked",
    "duplicates",
    "status",
    "link",
    "attachments",
    "mah_id",
    "year",
    "view",
    "rules",
    "sort",
    "direction",
    "layout",
    "preset",
    "declaration_lookup",
    "page",
    "page_size",
}


def clean_context(query):
    if len(query) > 12000:
        return ""
    try:
        pairs = parse_qsl(query.lstrip("?"), max_num_fields=100, keep_blank_values=True)
    except ValueError:
        return ""
    return urlencode([(k, v) for k, v in pairs if k in CONTEXT_KEYS or k.startswith("tv_")])


def related_record_url(request, path, section=""):
    """Called with application-owned destination paths, never a user return URL."""
    match = re.fullmatch(r"/crm/([a-z-]+)/([1-9][0-9]*)", request.url.path)
    if not match or match[1] not in MODELS:
        return path
    context = clean_context(request.url.query)
    query = {"origin": f"{match[1]}:{match[2]}", "origin_context": context}
    if section in ("contacts", "contract", "related-records"):
        query["origin_section"] = section
    return path + ("&" if "?" in path else "?") + urlencode(query)


def crm_record_origin(request, session):
    raw = request.query_params.get("origin", "")
    match = re.fullmatch(r"([a-z-]+):([1-9][0-9]{0,17})", raw)
    if not match or match[1] not in MODELS:
        return None
    model, label, attribute = MODELS[match[1]]
    record = session.get(model, int(match[2]))
    if record is None:
        return None
    try:
        context = clean_context(request.query_params.get("origin_context", ""))
    except ValueError:
        context = ""
    section = request.query_params.get("origin_section", "")
    return {
        "path": f"/crm/{match[1]}/{record.id}"
        + (f"?{context}" if context else "")
        + (
            f"#{section}"
            if section in ("contacts", "contract", "related-records")
            else ""
        ),
        "label": f"{label}: {getattr(record, attribute)}",
        "directory": match[1],
        "record": record,
    }
