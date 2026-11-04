"""Reuse one successful extraction per source/content/parser/transform identity."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db.models import AcquiredArtifact, ArtifactContent, ProcessingRun
from app.core.db.session import require_runtime_session


def reusable_result(
    session: Session, artifact: AcquiredArtifact, run: ProcessingRun
) -> ProcessingRun | None:
    require_runtime_session(session)
    # Lock until staging and success commit together. The content row exists before
    # processing; identical concurrent downloads therefore share this mutex.
    session.execute(
        select(ArtifactContent.id)
        .where(ArtifactContent.id == artifact.content_id)
        .with_for_update()
    ).scalar_one()
    # Use a current locking read, not a stale MySQL REPEATABLE READ snapshot.
    return session.scalar(
        select(ProcessingRun)
        .join(AcquiredArtifact)
        .where(
            AcquiredArtifact.content_id == artifact.content_id,
            AcquiredArtifact.source_name == artifact.source_name,
            AcquiredArtifact.channel_name == artifact.channel_name,
            AcquiredArtifact.report_type == artifact.report_type,
            ProcessingRun.parser_version == run.parser_version,
            ProcessingRun.transform_version == run.transform_version,
            ProcessingRun.status == "succeeded",
            ProcessingRun.reused_from_run_id.is_(None),
            ProcessingRun.id != run.id,
        )
        .order_by(ProcessingRun.id)
        .limit(1)
        .with_for_update()
    )


def result_run_id(run: ProcessingRun) -> int:
    return run.reused_from_run_id or run.id
