"""Internal pull worker: public intake never connects to the Operations database."""

import argparse
import json
import time
from urllib.parse import urlsplit

import httpx
from cryptography.fernet import InvalidToken
from sqlalchemy.exc import SQLAlchemyError

from app.core.http.sensitive import sensitive_http_request
from app.domain.crm.registrations import import_intake, purge_expired


def configuration(settings):
    url = (settings.registration_intake_url or "").rstrip("/")
    p = urlsplit(url)
    if (
        not p.hostname
        or p.username
        or p.password
        or p.path
        or p.query
        or p.fragment
        or not (
            p.scheme == "https"
            or (
                settings.environment == "development"
                and p.scheme == "http"
                and p.hostname == "localhost"
            )
        )
    ):
        raise ValueError(
            "Configure the canonical HTTPS intake URL, or localhost for development."
        )
    if (
        not settings.registration_exchange_secret
        or not settings.registration_encryption_key
    ):
        raise ValueError("Configure the registration exchange and encryption secrets.")
    return (
        url,
        settings.registration_exchange_secret.get_secret_value(),
        settings.registration_encryption_key.get_secret_value(),
    )


def pull(factory, settings):
    base, secret, key = configuration(settings)
    with factory.begin() as s:
        purge_expired(s)
    count = 0
    with (
        sensitive_http_request(),
        httpx.Client(
            timeout=15,
            trust_env=False,
            follow_redirects=False,
            headers={"Authorization": "Bearer " + secret},
        ) as client,
    ):
        with client.stream("GET", base + "/exchange/registrations") as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                if len(body) + len(chunk) > 2 * 1024 * 1024:
                    raise ValueError("Intake response exceeds its limit.")
                body.extend(chunk)
        rows = json.loads(body)["registrations"]
        if not isinstance(rows, list) or len(rows) > 100:
            raise ValueError("Invalid intake response.")
        for data in rows:
            with factory.begin() as session:
                import_intake(session, data, key)
            # Acknowledge only AFTER the core transaction has committed.
            ack = client.post(
                base + "/exchange/registrations/ack",
                json={"id": data["id"], "revision": data["revision"]},
            )
            ack.raise_for_status()
            count += 1
    return count


def main():
    from app.core.config import get_settings
    from app.core.db.session import get_session_factory

    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    while True:
        try:
            print(
                f"{pull(get_session_factory(), get_settings())} registration revisions synchronised.",
                flush=True,
            )
        except (
            httpx.HTTPError,
            ValueError,
            KeyError,
            TypeError,
            InvalidToken,
            SQLAlchemyError,
        ):
            print(
                "Registration synchronisation failed. Check configuration and intake availability.",
                flush=True,
            )
        if not args.watch:
            break
        time.sleep(30)


if __name__ == "__main__":
    main()


def resend_confirmation(settings, identifier, revision):
    base, secret, _ = configuration(settings)
    with (
        sensitive_http_request(),
        httpx.Client(timeout=15, trust_env=False, follow_redirects=False) as client,
    ):
        response = client.post(
            base + "/exchange/registrations/resend",
            headers={"Authorization": "Bearer " + secret},
            json={"id": identifier, "revision": revision},
        )
        response.raise_for_status()
