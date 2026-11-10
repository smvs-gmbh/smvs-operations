"""Internal confirmation outbox and cleanup; uses only the core DB, no public pull."""

import argparse
import time

from cryptography.fernet import InvalidToken
from sqlalchemy.exc import SQLAlchemyError

from app.domain.models import RegistrationReceipt
from app.registration.internal_service import synchronise_pending
from app.registration.mail import send_pending


def process(factory, settings, *, mail=True, receipt_id=None):
    key = settings.registration_encryption_key.get_secret_value()
    with factory.begin() as session:
        synchronise_pending(session, key)
    try:
        return (
            send_pending(
                factory, settings, model=RegistrationReceipt, only_id=receipt_id
            )
            if mail
            else 0
        )
    finally:
        with factory.begin() as session:
            synchronise_pending(session, key)


def main():
    from app.core.db.session import get_session_factory
    from app.registration.internal_settings import InternalRegistrationSettings

    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--purge-only", action="store_true")
    parser.add_argument(
        "--receipt-id", help="Send only this receipt, for controlled acceptance tests."
    )
    args = parser.parse_args()
    if args.receipt_id and (args.purge_only or args.watch):
        parser.error(
            "--receipt-id requires a single mail run without --watch or --purge-only."
        )
    settings = InternalRegistrationSettings()
    while True:
        try:
            count = process(
                get_session_factory(),
                settings,
                mail=not args.purge_only,
                receipt_id=args.receipt_id,
            )
            print(f"{count} confirmation emails accepted by SendGrid.", flush=True)
        except (ValueError, OSError, InvalidToken, SQLAlchemyError):
            print(
                "Registration worker failed. Check internal configuration.", flush=True
            )
        if not args.watch:
            break
        time.sleep(30)


if __name__ == "__main__":
    main()
