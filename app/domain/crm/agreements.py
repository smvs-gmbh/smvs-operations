"""Archive original MAH agreement PDFs from a supplied Airtable export."""

import hashlib
import re
from collections import defaultdict
from datetime import date, datetime
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select

from app.core.db.models import (
    AcquiredArtifact,
    ArtifactContent,
    IntegrationJob,
    StagingDataset,
    StagingRow,
)
from app.domain.crm.imports import SOURCE, linked_values, staged_crm_export
from app.domain.models import CRMAgreement, CRMMah
from app.integration.artifacts.storage import MySQLArtifactStore, utcnow

REPORT_TYPE = "MAH Agreement PDF"
MANUAL_SOURCE = "SMVS Operations CRM"
AGREEMENT_PDF_SOURCES = (SOURCE, MANUAL_SOURCE)
AGREEMENT_STATUSES = ("Signed", "Terminated", "Transferred")
ATTACHMENTS = re.compile(r'("?)(.+?)\s+\((https://[^\s()]+)\)\1(?:,\s*|$)')
MAX_PDF_BYTES = 12 * 1024 * 1024


def download_pdf(client, url):
    parts = urlsplit(url)
    if parts.netloc != "v5.airtableusercontent.com" or parts.scheme != "https":
        raise ValueError("Unsupported Airtable attachment host.")
    content = bytearray()
    with client.stream("GET", url) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            if len(content) + len(chunk) > MAX_PDF_BYTES:
                raise ValueError("Attachment exceeds the PDF size limit.")
            content.extend(chunk)
    if not content.startswith(b"%PDF-"):
        raise ValueError("Attachment is not a PDF.")
    return bytes(content)


def archive_pdf(session, contract_id, filename, content, *, source=SOURCE):
    stored = MySQLArtifactStore._get_or_create_content(
        session, hashlib.sha256(content).hexdigest(), content
    )
    session.scalar(
        select(ArtifactContent.id)
        .where(ArtifactContent.id == stored.id)
        .with_for_update()
    )
    metadata = {"contract_id": contract_id, "filename": filename}
    existing = session.scalars(
        select(AcquiredArtifact.report_metadata)
        .where(
            AcquiredArtifact.source_name.in_(AGREEMENT_PDF_SOURCES),
            AcquiredArtifact.report_type == REPORT_TYPE,
            AcquiredArtifact.content_id == stored.id,
        )
        .with_for_update()
    )
    if metadata in existing:
        return False

    now = utcnow()
    job = IntegrationJob(
        source_name=source,
        channel_name="Airtable attachment" if source == SOURCE else "Portal upload",
        report_type=REPORT_TYPE,
        status="succeeded",
        started_at=now,
        completed_at=now,
        created_at=now,
    )
    session.add(
        AcquiredArtifact(
            integration_job=job,
            content=stored,
            source_name=source,
            channel_name=job.channel_name,
            report_type=REPORT_TYPE,
            content_type="application/pdf",
            report_metadata=metadata,
            received_at=now,
            created_at=now,
            processing_status="acquired",
        )
    )
    return True


def archive_pdfs(factory, rows):
    saved = reused = failed = 0
    with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
        for row in rows:
            field = row.get("Agreement", "").strip()
            offset = 0
            for match in ATTACHMENTS.finditer(field):
                if match.start() != offset:
                    failed += 1
                offset = match.end()
                _, filename, url = match.groups()
                try:
                    content = download_pdf(client, url)
                except (httpx.HTTPError, ValueError):
                    failed += 1
                    continue
                with factory() as session, session.begin():
                    if archive_pdf(
                        session, row["Contract ID"].strip(), filename.strip(), content
                    ):
                        saved += 1
                    else:
                        reused += 1
            if offset != len(field):
                failed += 1
    print(
        f"Agreement PDFs: {saved} archived, {reused} already archived, {failed} unavailable.",
        flush=True,
    )
    return failed


def agreement_candidates(session):
    candidates = defaultdict(list)
    for mah, raw in session.execute(
        select(CRMMah, StagingRow.raw_row_json)
        .join(StagingRow, CRMMah.source_row_id == StagingRow.id)
        .where(CRMMah.archived_at.is_(None))
        .order_by(CRMMah.name, CRMMah.id)
    ):
        for contract_id in dict.fromkeys(linked_values(raw.get("Agreements", ""))):
            candidates[contract_id].append(mah)
    return candidates


def seed_agreements(session):
    export = staged_crm_export(session, "MAH Agreements")
    if export is None:
        raise ValueError("Stage a MAH Agreements export first.")
    dataset, _, _, rows = export
    session.scalar(
        select(StagingDataset.id)
        .where(StagingDataset.id == dataset.id)
        .with_for_update()
    )
    existing = set(session.scalars(select(CRMAgreement.contract_id).with_for_update()))
    candidates = agreement_candidates(session)
    created = 0
    for row in rows:
        raw = row.raw_row_json
        contract_id = raw["Contract ID"].strip()
        if contract_id in existing:
            continue
        matches = candidates[contract_id]
        value = (raw.get("Signing Date") or "").strip()
        signing_date = None
        if value:
            signing_date = (
                datetime.strptime(value, "%d.%m.%Y").date()  # noqa: DTZ007 - calendar date only
                if "." in value
                else date.fromisoformat(value)
            )
        session.add(
            CRMAgreement(
                contract_id=contract_id,
                contractor=raw["Contractor"].strip(),
                status=raw["Status"].strip(),
                signing_date=signing_date,
                mahs=matches if len(matches) == 1 else [],
                source_row_id=row.id,
            )
        )
        created += 1
    return created


def main():
    from app.core.db.session import SessionFactory

    with SessionFactory() as session, session.begin():
        count = seed_agreements(session)
    print(f"{count} agreements created.")


if __name__ == "__main__":
    main()
