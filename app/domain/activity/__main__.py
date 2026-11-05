import argparse
from datetime import date, timedelta

from app.core.db.session import SessionFactory
from app.domain.activity.service import import_period, scheduled_import
from app.integration.sources.nmvs.activity.api import UserActivityClient
from app.integration.sources.nmvs.connection import reporting_client


def main():
    parser = argparse.ArgumentParser(
        description="Import and publish genuine NMVS activity (UTC days)."
    )
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--catch-up", action="store_true")
    args = parser.parse_args()
    if (
        args.catch_up
        and (args.start or args.end)
        or not args.catch_up
        and not (args.start and args.end)
    ):
        parser.error("Use --catch-up or both --start and --end.")
    try:
        if args.catch_up:
            job = scheduled_import(SessionFactory)
            print({"last_job_id": job.id if job else None}, flush=True)
        else:
            client = reporting_client(UserActivityClient)
            try:
                start = args.start
                while start <= args.end:
                    end = min(start + timedelta(days=29), args.end)
                    job, pub = import_period(SessionFactory, client, start, end)
                    print(
                        {
                            "job_id": job,
                            "publication_id": pub.id,
                            "start": start.isoformat(),
                            "end": end.isoformat(),
                            "statistics": pub.statistics,
                        },
                        flush=True,
                    )
                    start = end + timedelta(days=1)
            finally:
                client.close()
    except Exception:  # noqa: BLE001 - sanitize credentials and source/SQL diagnostics
        parser.exit(
            1,
            "Activity import failed; inspect execution records and source availability.\n",
        )


if __name__ == "__main__":
    main()
