"""Manage the separate public intake store and mail worker."""

import argparse
import time

from cryptography.fernet import InvalidToken
from sqlalchemy.exc import SQLAlchemyError

from app.registration.mail import send_pending
from app.registration.service import purge
from app.registration.settings import IntakeSettings
from app.registration.store import factory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["init", "mail-once", "mail-watch", "purge"])
    args = parser.parse_args()
    settings = IntakeSettings()
    sessions = factory(settings, initialise=args.command == "init")
    if args.command == "init":
        return
    if args.command == "purge":
        with sessions.begin() as s:
            purge(s)
        return
    while True:
        try:
            print(
                f"{send_pending(sessions, settings)} confirmation emails accepted by SendGrid.",
                flush=True,
            )
        except (ValueError, OSError, InvalidToken, SQLAlchemyError):
            print("Registration mail configuration is incomplete.", flush=True)
        if args.command != "mail-watch":
            break
        time.sleep(30)


if __name__ == "__main__":
    main()
