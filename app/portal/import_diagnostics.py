"""Read-only, bounded diagnostics from retained import records, never raw logs."""

import re

from sqlalchemy import select

from app.core.db.models import AcquiredArtifact, IntegrationJob, ProcessingRun

FAILURES = {
    "worker_interrupted": (
        "The worker stopped before it recorded the outcome of this import.",
        "The exact cause was not recorded. Check the worker and server logs for this period; possible causes include memory exhaustion, a service restart or external termination.",
    ),
    "parse_error": (
        "The downloaded source could not be parsed.",
        "Review the retained source format and parser compatibility before retrying.",
    ),
    "reporting_api_error": (
        "The source API returned an unusable report response.",
        "Check source availability and report configuration before retrying.",
    ),
    "http_error": (
        "A source request failed.",
        "Check network connectivity, source availability and connection configuration.",
    ),
    "database_error": (
        "A database operation failed.",
        "Check database availability and the server logs for this period.",
    ),
    "database_safety": (
        "Database safety verification failed.",
        "Review the configured database and its identity before retrying.",
    ),
    "invalid_data": (
        "The supplied data failed validation.",
        "Review the source records and required configuration before retrying.",
    ),
    "publication_error": (
        "The source was retrieved, but publication did not complete.",
        "Review the selected references and mapping history. A successful download alone does not confirm publication.",
    ),
    "processing_error": (
        "The import could not complete.",
        "Review the retained processing records and server logs for this period.",
    ),
}
STAGES = {
    "acquisition_start": "Starting acquisition",
    "discovery": "Discovering the source export",
    "acquisition": "Retrieving the source",
    "processing_start": "Starting source processing",
    "extraction": "Extracting source records",
    "staging": "Storing extracted records",
    "publication": "Publishing the working dataset",
}
STATUSES = {
    "acquiring": "Retrieving the source",
    "artifact_acquired": "Source retrieved; processing not confirmed",
    "extracting": "Extraction started; completion not recorded",
    "staging": "Staging started; completion not recorded",
    "succeeded": "Source processing completed",
    "failed": "Failed",
}


def code(value):
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,99}", value)
        else "Not recorded"
    )


def execution_details(session, execution, report_type):
    reason, action = FAILURES.get(
        execution.failure_code,
        (
            "No further diagnostic explanation was recorded.",
            "Review the worker and server logs for this period.",
        ),
    )
    facts = [
        ("Execution ID", str(execution.id)),
        ("Failure code", code(execution.failure_code)),
    ]
    if execution.completed_at:
        seconds = max(
            0, int((execution.completed_at - execution.started_at).total_seconds())
        )
        facts.append(
            (
                "Time until interruption detected"
                if execution.status == "interrupted"
                else "Elapsed time",
                f"{seconds} seconds",
            )
        )
    linked = execution.integration_job_id is not None
    if linked:
        job = session.get(IntegrationJob, execution.integration_job_id)
        jobs = [job] if job else []
    elif execution.completed_at and report_type:
        # Crashed workers may never have linked their source job. A time-window
        # match is contextual evidence, not proof of ownership or of a kill cause.
        jobs = session.scalars(
            select(IntegrationJob)
            .where(
                IntegrationJob.report_type == report_type,
                IntegrationJob.created_at >= execution.started_at,
                IntegrationJob.created_at < execution.completed_at,
            )
            .order_by(IntegrationJob.id)
            .limit(2)
        ).all()
    else:
        jobs = []
    sections = []
    note = "No linked source job was recorded."
    if len(jobs) > 1:
        note = "Several source jobs were recorded in this time window; none can be assigned reliably to this execution."
    elif jobs:
        job = jobs[0]
        note = (
            "Source job explicitly linked to this execution."
            if linked
            else "Source activity recorded in the same time window. It was not explicitly linked to this execution."
        )
        job_facts = [
            ("Source job ID", str(job.id)),
            ("Recorded source status", STATUSES.get(job.status, "Not recorded")),
        ]
        if job.failure_stage:
            job_facts.append(
                ("Failure stage", STAGES.get(job.failure_stage, "Not recorded"))
            )
        if job.failure_code:
            job_facts.append(("Source failure code", code(job.failure_code)))
        sections.append(("Source acquisition", job_facts))
        runs = session.scalars(
            select(ProcessingRun)
            .join(AcquiredArtifact)
            .where(
                AcquiredArtifact.integration_job_id == job.id,
                ProcessingRun.started_at >= execution.started_at,
                ProcessingRun.started_at
                <= (execution.completed_at or execution.started_at),
            )
            .order_by(ProcessingRun.id.desc())
            .limit(3)
        ).all()
        for run in runs:
            run_facts = [
                ("Processing run ID", str(run.id)),
                (
                    "Recorded processing status",
                    STATUSES.get(run.status, "Not recorded"),
                ),
            ]
            if run.failure_stage:
                run_facts.append(
                    ("Failure stage", STAGES.get(run.failure_stage, "Not recorded"))
                )
            if run.failure_code:
                run_facts.append(("Processing failure code", code(run.failure_code)))
            if run.reused_from_run_id:
                run_facts.append(
                    ("Reused processing result", str(run.reused_from_run_id))
                )
            sections.append(("Source processing", run_facts))
    return {
        "reason": reason,
        "action": action,
        "facts": facts,
        "sections": sections,
        "note": note,
    }
