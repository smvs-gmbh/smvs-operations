"""Private staff reader for captured hosted TEST mail, never public delivery."""

import os
import re
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path

from fastapi import HTTPException

from app.alert_desk.mail_settings import MailSettings
from app.alert_desk.settings import AlertDeskSettings
from app.core.config import get_settings
from app.portal.routes import templates

PRIVATE = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
IDENTIFIER = re.compile(r"[a-f0-9]{32}")


def directory(request):
    from app.portal.collaboration_routes import require_invitation_staff

    settings = get_settings()
    if settings.environment != "test" or not settings.alert_desk_test_enabled:
        raise HTTPException(404, "TEST mailbox is unavailable.")
    require_invitation_staff(request)
    root = os.environ.get("SMVS_TEST_ROOT")
    if not root or not Path(root).is_absolute():
        raise HTTPException(503, "TEST mailbox is not configured.")
    return Path(root) / "private/mail"


def read(path):
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            raw = stream.read(128 * 1024 + 1)
        if len(raw) > 128 * 1024:
            raise ValueError()
        message = BytesParser(policy=policy.default).parsebytes(raw)
        part = message.get_body(preferencelist=("plain",))
        body = part.get_content() if part else "No plain-text content."
        return {
            "id": path.stem, "subject": str(message.get("Subject", "No subject")),
            "to": str(message.get("To", "")), "body": body,
            "at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }
    except (OSError, ValueError, LookupError, UnicodeError):
        raise HTTPException(404, "Captured message is unavailable.") from None


def page(request, identifier=None):
    folder = directory(request)
    selected = None
    messages = []
    if identifier is not None:
        if not IDENTIFIER.fullmatch(identifier):
            raise HTTPException(404, "Captured message is unavailable.")
        selected = read(folder / (identifier + ".eml"))
        origin = AlertDeskSettings().alert_desk_public_origin
        pattern = re.escape(origin + "/alerts/access#") + r"[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])"
        match = re.search(pattern, selected["body"])
        selected["invitation_url"] = match.group() if match else None
    else:
        try:
            paths = sorted(
                (p for p in folder.glob("*.eml") if IDENTIFIER.fullmatch(p.stem) and not p.is_symlink()),
                key=lambda p: p.stat().st_mtime, reverse=True,
            )[:100]
        except OSError:
            raise HTTPException(503, "TEST mailbox is unavailable.") from None
        for path in paths:
            try:
                item = read(path)
                item.pop("body")
                messages.append(item)
            except HTTPException:
                continue
    return templates.TemplateResponse(
        request=request, name="alert_desk_test_mailbox.html", headers=PRIVATE,
        context={"title": "TEST mailbox", "active": "workflows",
                 "messages": messages, "message": selected, "mail_mode": MailSettings().alert_desk_mail_mode},
    )
