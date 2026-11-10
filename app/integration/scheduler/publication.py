"""Complete current Snapshot imports using the already selected SAI reference."""

from sqlalchemy import select

from app.core.db.models import AcquiredArtifact, ProcessingRun
from app.domain.mapping import publish
from app.domain.models import CurrentPublication, MappingRun
from app.domain.participants.mapping import publish_participants


def publish_snapshot(factory, job_id):
    with factory() as session:
        current = session.get(CurrentPublication, "product-batch")
        if not current:
            raise ValueError("Select the initial Snapshot/SAI publication first.")
        previous = session.get(MappingRun, current.mapping_run_id)
        if not previous or previous.status != "succeeded":
            raise ValueError("The selected SAI reference is unavailable.")
        run_id = session.scalar(
            select(ProcessingRun.id)
            .join(AcquiredArtifact, ProcessingRun.artifact_id == AcquiredArtifact.id)
            .where(
                AcquiredArtifact.integration_job_id == job_id,
                AcquiredArtifact.source_name == "NMVS",
                AcquiredArtifact.report_type == "DailySnapshot",
                ProcessingRun.status == "succeeded",
            )
            .order_by(ProcessingRun.id.desc())
            .limit(1)
        )
        if run_id is None:
            raise ValueError("Snapshot processing has not succeeded.")
        namespace, sai_id = current.source_namespace, previous.sai_run_id
    # Both publishers guard against rollback, namespace changes and implicit
    # same-day corrections. Each is idempotent, including retry after partial success.
    products = publish(factory, run_id, sai_id, namespace)
    participants = publish_participants(factory, run_id, namespace)
    return products.id, participants.id
