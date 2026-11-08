"""Stage Airtable exports for field review before CRM mapping."""

import csv
import hashlib
import io
from collections import Counter

from sqlalchemy import select

from app.core.db.models import (
    AcquiredArtifact,
    ArtifactContent,
    IntegrationJob,
    ProcessingRun,
    StagingDataset,
    StagingRow,
)
from app.core.db.session import require_runtime_session
from app.integration.artifacts.storage import MySQLArtifactStore, utcnow
from app.integration.sources.nmvs.parsing import ExtractedDataset, ParsedDailySnapshot
from app.integration.staging.service import stage_daily_snapshot

SOURCE = "Airtable CRM"
CHANNEL = "Provided CSV"
PARSER_VERSION = "airtable-csv-v1"
TABLES = {
    "MAH": ("RECORD_ID", "MAH Name"),
    "Contacts": ("RECORD_ID2", "Record Id"),
    "End Users": ("Record Id", "End User Name"),
    "IT Suppliers": ("Record Id", "IT Supplier Name"),
    "MAH Agreements": ("Contract ID", "Contractor"),
    "Self-declarations": ("Record Id", "MAH Name"),
}


def parse_export(table, content):
    id_field, label_field = TABLES[table]
    reader = csv.reader(
        io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True
    )
    headers = next(reader, [])
    if (
        not headers
        or any(not header.strip() for header in headers)
        or len(set(headers)) != len(headers)
    ):
        raise ValueError(f"{table} export has missing or duplicate column names.")
    if not {id_field, label_field}.issubset(headers):
        raise ValueError(f"{table} export needs {id_field} and {label_field}.")
    if table == "Self-declarations" and not {
        "Declaration year",
        "RX packs sold",
    }.issubset(headers):
        raise ValueError(
            "Self-declarations export needs Declaration year and RX packs sold."
        )
    rows = []
    ids = set()
    for index, values in enumerate(reader, start=1):
        if not values:
            continue
        if len(values) != len(headers):
            raise ValueError(f"{table} record {index} has the wrong column count.")
        row = dict(zip(headers, values, strict=True))
        identity = row[id_field].strip()
        if not identity or (
            table not in ("End Users", "Self-declarations") and identity in ids
        ):
            raise ValueError(
                f"{table} record {index} has a missing or duplicate {id_field}."
            )
        ids.add(identity)
        rows.append(row)
    if not rows:
        raise ValueError(f"{table} export contains no records.")
    return ExtractedDataset(table, 1, tuple(headers), tuple(rows))


def stage_export(session, dataset, content, filename):
    require_runtime_session(session)
    now = utcnow()
    stored = MySQLArtifactStore._get_or_create_content(
        session, hashlib.sha256(content).hexdigest(), content
    )
    # Serialise identical imports on their shared content row.
    session.scalar(
        select(ArtifactContent.id)
        .where(ArtifactContent.id == stored.id)
        .with_for_update()
    )
    existing = session.scalar(
        select(StagingDataset)
        .join(ProcessingRun, ProcessingRun.id == StagingDataset.processing_run_id)
        .join(AcquiredArtifact, AcquiredArtifact.id == ProcessingRun.artifact_id)
        .where(
            AcquiredArtifact.content_id == stored.id,
            AcquiredArtifact.source_name == SOURCE,
            AcquiredArtifact.report_type == dataset.source_dataset_name,
            ProcessingRun.parser_version == PARSER_VERSION,
            ProcessingRun.status == "staged",
        )
        .with_for_update()
    )
    if existing:
        return existing, False
    job = IntegrationJob(
        source_name=SOURCE,
        channel_name=CHANNEL,
        report_type=dataset.source_dataset_name,
        status="succeeded",
        started_at=now,
        completed_at=now,
        created_at=now,
    )
    session.add(job)
    session.flush()
    artifact = AcquiredArtifact(
        integration_job_id=job.id,
        content=stored,
        source_name=SOURCE,
        channel_name=CHANNEL,
        report_type=dataset.source_dataset_name,
        content_type="text/csv",
        report_metadata={"filename": filename},
        received_at=now,
        created_at=now,
        processing_status="staged",
    )
    session.add(artifact)
    session.flush()
    run = ProcessingRun(
        artifact_id=artifact.id,
        run_type="initial_extraction",
        parser_version=PARSER_VERSION,
        transform_version="raw",
        status="staged",
        started_at=now,
        completed_at=now,
    )
    session.add(run)
    session.flush()
    stage_daily_snapshot(session, artifact, ParsedDailySnapshot({}, (dataset,)), run)
    return run.datasets[0], True


def linked_values(value):
    try:
        return [
            label.strip()
            for label in next(csv.reader([value], strict=True), [])
            if label.strip()
        ]
    except csv.Error:
        return [value.strip()] if value.strip() else []


def relation_profile(rows, field, target_labels):
    counts = Counter()
    for row in rows:
        for value in linked_values(row.get(field, "")):
            matches = target_labels[value]
            counts[
                "unique" if matches == 1 else "ambiguous" if matches > 1 else "missing"
            ] += 1
    return counts


def staged_crm_metadata(session, table):
    return session.execute(
        select(
            StagingDataset,
            AcquiredArtifact.report_metadata,
            AcquiredArtifact.received_at,
        )
        .join(AcquiredArtifact, AcquiredArtifact.id == StagingDataset.artifact_id)
        .join(ProcessingRun, ProcessingRun.id == StagingDataset.processing_run_id)
        .where(
            AcquiredArtifact.source_name == SOURCE,
            AcquiredArtifact.report_type == table,
            ProcessingRun.status == "staged",
        )
        .order_by(StagingDataset.id.desc())
        .limit(1)
    ).first()


def staged_crm_export(session, table):
    result = staged_crm_metadata(session, table)
    if not result:
        return None
    dataset, metadata, received = result
    staged_rows = list(
        session.scalars(
            select(StagingRow)
            .where(StagingRow.staging_dataset_id == dataset.id)
            .order_by(StagingRow.source_row_number, StagingRow.id)
        )
    )
    return dataset, metadata, received, staged_rows
