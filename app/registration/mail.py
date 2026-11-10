"""Explicit mail worker; webhook acknowledgement never waits for SendGrid."""

import re

import httpx
from sqlalchemy import select

from app.registration.crypto import decrypt
from app.registration.models import IntakeRegistration
from app.registration.service import now, purge


def send_pending(factory, settings, *, model=IntakeRegistration, only_id=None):
    if not settings.sendgrid_api_key or not re.fullmatch(
        r"[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+", settings.registration_mail_from
    ):
        raise ValueError("Configure SendGrid and the verified registration sender.")
    if (
        not settings.registration_mail_link_field
        or not settings.registration_mail_template.startswith("d-")
    ):
        raise ValueError("Configure the SendGrid dynamic template.")
    with factory.begin() as session:
        purge(session, model=model)
    with factory() as session:
        statement = (
            select(model.id)
            .where(
                model.mail_status == "queued",
                model.token_expires_at > now(),
                model.confirmed_at.is_(None),
            )
            .order_by(model.received_at)
            .limit(50)
        )
        if only_id is not None:
            statement = statement.where(model.id == only_id)
        ids = list(session.scalars(statement))
    accepted = 0
    for identifier in ids:
        # Claim durably before network I/O. An uncertain delivery is NOT retried automatically.
        with factory.begin() as session:
            row = session.get(model, identifier, with_for_update=True)
            if (
                row.mail_status != "queued"
                or row.confirmed_at
                or row.token_expires_at <= now()
            ):
                continue
            values = decrypt(
                settings.registration_encryption_key.get_secret_value(),
                row.payload_ciphertext,
            )
            token = decrypt(
                settings.registration_encryption_key.get_secret_value(),
                row.token_ciphertext,
            )["token"]
            link = settings.registration_public_origin + "/confirm#" + token
            dynamic = {
                "organisation_name": values["name"],
                "first_name": values["first_name"],
                "last_name": values["last_name"],
                settings.registration_mail_link_field: link,
            }
            payload = {
                "from": {"email": settings.registration_mail_from},
                "template_id": settings.registration_mail_template,
                "personalizations": [
                    {
                        "to": [{"email": values["email"]}],
                        "dynamic_template_data": dynamic,
                    }
                ],
                "tracking_settings": {
                    "click_tracking": {"enable": False, "enable_text": False},
                    "open_tracking": {"enable": False},
                },
            }
            row.mail_status = "sending"
            row.revision += 1
            row.mail_attempts += 1
            row.mail_attempted_at = now()
        try:
            with httpx.Client(
                timeout=15, trust_env=False, follow_redirects=False
            ) as client:
                response = client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    headers={
                        "Authorization": "Bearer "
                        + settings.sendgrid_api_key.get_secret_value()
                    },
                    json=payload,
                )
            status = (
                "accepted"
                if response.status_code == 202
                else "failed"
                if 400 <= response.status_code < 500
                else "uncertain"
            )
        except httpx.HTTPError:
            status = "uncertain"
        with factory.begin() as session:
            row = session.get(model, identifier, with_for_update=True)
            row.mail_status = status
            row.revision += 1
            if status == "accepted":
                row.mail_sent_at = now()
                accepted += 1
    return accepted
