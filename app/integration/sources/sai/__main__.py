"""Run with: python -m app.integration.sources.sai [--replay ARTIFACT_ID]."""

import argparse
import json

from sqlalchemy import select

from app.core.db.models import AcquiredArtifact, ProcessingRun, StagingDataset
from app.core.db.session import SessionFactory
from app.integration.failures import IntegrationExecutionError
from app.integration.idempotency import result_run_id
from app.integration.sources.sai.acquisition import SAIAcquisition
from app.integration.sources.sai.client import SAIClient
from app.integration.sources.sai.processing import replay_sai


def main():
    parser = argparse.ArgumentParser(
        description="Import the latest full Refdata SAI export."
    )
    parser.add_argument("--replay", type=int, metavar="ARTIFACT_ID")
    args = parser.parse_args()
    client = SAIClient()
    try:
        with SessionFactory() as session:
            if args.replay is not None:
                run = replay_sai(session, args.replay)
            else:
                job = SAIAcquisition(client).run(session)
                run = session.scalar(
                    select(ProcessingRun)
                    .join(AcquiredArtifact)
                    .where(AcquiredArtifact.integration_job_id == job.id)
                    .order_by(ProcessingRun.id.desc())
                )
            datasets = session.scalars(
                select(StagingDataset).where(StagingDataset.processing_run_id == result_run_id(run))
            ).all()
            print(
                json.dumps(
                    {
                        "artifact_id": run.artifact_id,
                        "processing_run_id": run.id,
                        "status": run.status,
                        "result_run_id": result_run_id(run),
                        "reused": run.reused_from_run_id is not None,
                        "datasets": {
                            d.source_dataset_name: d.row_count for d in datasets
                        },
                    }
                )
            )
    except IntegrationExecutionError as error:
        parser.exit(1, f"SAI import failed: {error}\n")
    except Exception:  # noqa: BLE001 - never expose configuration or driver secrets
        parser.exit(
            1,
            "SAI import could not start; verify configuration and database readiness.\n",
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
