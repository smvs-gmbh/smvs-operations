import argparse
from datetime import date

from app.core.db.session import SessionFactory
from app.domain.exceptions.service import import_days


def main():
    p = argparse.ArgumentParser(
        description="Acquire source exceptions and publish observations, without changing investigations."
    )
    p.add_argument("--start", type=date.fromisoformat, required=True)
    p.add_argument("--end", type=date.fromisoformat, required=True)
    a = p.parse_args()
    try:
        import_days(
            SessionFactory,
            a.start,
            a.end,
            progress=lambda j, pub: print(
                {
                    "job_id": j,
                    "publication_id": pub.id,
                    "start": pub.period_start.isoformat(),
                    "end": pub.period_end.isoformat(),
                    "statistics": pub.statistics,
                },
                flush=True,
            ),
        )
    except Exception:  # noqa: BLE001 - suppress raw source and SQL diagnostics
        p.exit(1, "Exception import failed; inspect acquisition/extraction records.\n")


if __name__ == "__main__":
    main()
