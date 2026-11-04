import argparse
import json

from app.core.db.session import get_session_factory
from app.domain.mapping import MappingError, publish


def main():
    parser = argparse.ArgumentParser(
        description="Publish the selected NMVS Snapshot + SAI Product/Batch working set."
    )
    parser.add_argument("--snapshot-run", type=int, required=True)
    parser.add_argument("--sai-run", type=int, required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--allow-same-day-correction", action="store_true")
    args = parser.parse_args()
    try:
        run = publish(
            get_session_factory(),
            args.snapshot_run,
            args.sai_run,
            args.namespace,
            allow_same_day_correction=args.allow_same_day_correction,
        )
        print(
            json.dumps(
                {
                    "mapping_run_id": run.id,
                    "status": run.status,
                    "statistics": run.statistics,
                }
            )
        )
    except MappingError as error:
        parser.exit(1, str(error) + "\n")
    except Exception:  # noqa: BLE001 - never expose database connection details
        parser.exit(1, "Mapping could not start; check configuration and migrations.\n")


if __name__ == "__main__":
    main()
