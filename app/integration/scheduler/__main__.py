import argparse
import json
import signal
import threading

from sqlalchemy import select

from app.core.db.models import ImportSchedule
from app.core.db.session import SessionFactory
from app.integration.scheduler.handlers import default_handlers
from app.integration.scheduler.service import ImportScheduler


def main():
    parser = argparse.ArgumentParser(description="SMVS Operations import scheduler")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--configure", metavar="IMPORT_KEY")
    actions.add_argument("--run", metavar="IMPORT_KEY")
    actions.add_argument("--tick", action="store_true")
    actions.add_argument("--serve", action="store_true")
    actions.add_argument("--list", action="store_true")
    parser.add_argument("--at", default="04:00")
    parser.add_argument("--timezone", default="Europe/Zurich")
    parser.add_argument("--enable", action="store_true")
    args = parser.parse_args()
    scheduler = ImportScheduler(SessionFactory, default_handlers())
    try:
        if args.configure:
            identifier = scheduler.configure(
                args.configure,
                daily_time=args.at,
                timezone=args.timezone,
                enabled=args.enable,
            )
            print(json.dumps({"schedule_id": identifier, "enabled": args.enable}))
        elif args.list:
            with SessionFactory() as session:
                schedules = session.scalars(
                    select(ImportSchedule).order_by(ImportSchedule.id)
                ).all()
                print(
                    json.dumps(
                        [
                            {
                                "id": s.id,
                                "import_key": s.import_key,
                                "enabled": bool(s.enabled),
                                "timezone": s.timezone,
                                "daily_time": s.daily_time,
                                "next_run_utc": s.next_run_at.isoformat(),
                            }
                            for s in schedules
                        ]
                    )
                )
        elif args.run:
            print(
                json.dumps({"execution_id": scheduler.execute(args.run, manual=True)})
            )
        elif args.tick:
            print(json.dumps({"execution_ids": scheduler.tick()}))
        else:
            stop = threading.Event()
            signal.signal(signal.SIGINT, lambda *_: stop.set())
            signal.signal(signal.SIGTERM, lambda *_: stop.set())
            while not stop.is_set():
                try:
                    scheduler.tick()
                except Exception:  # noqa: BLE001 - retry infrastructure on next poll, without leaking driver text
                    print(
                        "Scheduler tick failed; inspect database readiness.", flush=True
                    )
                stop.wait(15)
    except Exception:  # noqa: BLE001 - do not expose configuration or SQL parameter values
        parser.exit(
            1,
            "Scheduler operation failed; check configuration, migrations and execution records.\n",
        )


if __name__ == "__main__":
    main()
