from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select

from app.domain.mapping import key
from app.domain.models import (
    Batch,
    CurrentPublication,
    ExceptionPublication,
    ExceptionReview,
    ExceptionRevision,
    LocalLocation,
    LocalOrganisation,
    NMVSException,
    ParticipantPublication,
    ProductSourceRecord,
    SAIHolder,
    SAIPackage,
    SAIPreparation,
)
from app.portal.queries import paged


def namespace(session):
    p = session.get(ParticipantPublication, "participants")
    if p:
        return p.source_namespace
    return session.scalar(
        select(ExceptionPublication.source_namespace)
        .order_by(ExceptionPublication.id.desc())
        .limit(1)
    )


def context(session):
    ns = namespace(session)
    latest = session.scalar(
        select(ExceptionPublication)
        .where(ExceptionPublication.source_namespace == ns)
        .order_by(ExceptionPublication.captured_at.desc())
        .limit(1)
    )
    return {
        "exception_section": True,
        "publication": None,
        "source_namespace": ns,
        "latest_exception_publication": latest,
        "exception_total": session.scalar(
            select(func.count())
            .select_from(NMVSException)
            .where(NMVSException.source_namespace == ns)
        ),
        "unresolved_dates": session.scalar(
            select(func.count())
            .select_from(NMVSException)
            .where(
                NMVSException.source_namespace == ns, NMVSException.alert_at.is_(None)
            )
        ),
    }


def enriched(session, records):
    if not records:
        return []
    ns = records[0].source_namespace
    orgs = {
        o.source_organisation_id: o
        for o in session.scalars(
            select(LocalOrganisation).where(LocalOrganisation.source_namespace == ns)
        )
    }
    locations = {
        l.source_location_id: l
        for l in session.scalars(
            select(LocalLocation).where(LocalLocation.source_namespace == ns)
        )
    }
    source_keys = {
        key(ns, r.product_code_scheme, r.product_code)
        for r in records
        if r.product_code_scheme and r.product_code
    }
    products = {
        p.source_key: p
        for p in session.scalars(
            select(ProductSourceRecord).where(
                ProductSourceRecord.source_key.in_(source_keys),
                ProductSourceRecord.is_observed == 1,
            )
        )
    }
    publication = session.get(CurrentPublication, "product-batch")
    sai = defaultdict(list)
    if publication:
        statement = (
            select(SAIPackage, SAIPreparation, SAIHolder)
            .join(SAIPreparation, SAIPackage.preparation_id == SAIPreparation.id)
            .outerjoin(SAIHolder, SAIPreparation.holder_id == SAIHolder.id)
            .where(
                SAIPackage.gtin14.in_({r.gtin14 for r in records if r.gtin14}),
                SAIPackage.is_observed == 1,
                SAIPackage.last_mapping_run_id == publication.mapping_run_id,
            )
        )
        for row in session.execute(statement):
            sai[row[0].gtin14].append(row)
    reviews = {
        v.exception_id: v
        for v in session.scalars(
            select(ExceptionReview).where(
                ExceptionReview.exception_id.in_([r.id for r in records])
            )
        )
    }
    rows = []
    for r in records:
        match = sai.get(r.gtin14, [])
        package, preparation, holder = (
            match[0] if len(match) == 1 else (None, None, None)
        )
        product = products.get(key(ns, r.product_code_scheme, r.product_code))
        if (
            product
            and publication
            and (
                publication.source_namespace != ns
                or product.last_mapping_run_id != publication.mapping_run_id
            )
        ):
            product = None
        rows.append(
            {
                "record": r,
                "review": reviews.get(r.id),
                "name": preparation.preparation_name if preparation else None,
                "holder": holder.company_name if holder else None,
                "holder_id": holder.id if holder else None,
                "package": package,
                "product": product,
                "sai_status": "Matched to SAI"
                if len(match) == 1
                else "Multiple SAI matches"
                if match
                else "No SAI match"
                if r.gtin14
                else "No GTIN match",
                "organisation": orgs.get(r.organisation_id),
                "location": locations.get(r.source_location_id)
                if r.source_market in ("CH", "LI")
                else None,
                "last_update_location": locations.get(r.last_update_location_id)
                if r.evidence.get("packLastUpdateMarket") in ("CH", "LI")
                else None,
            }
        )
    return rows


def listing_statement(
    session,
    *,
    start,
    end,
    q="",
    error="",
    market="",
    organisation="",
    location="",
    process="",
    date_quality="",
    intermarket="",
    work_status="open",
):
    ns = namespace(session)
    statement = select(NMVSException).where(NMVSException.source_namespace == ns)
    statement = statement.outerjoin(
        ExceptionReview, ExceptionReview.exception_id == NMVSException.id
    )
    stale = ExceptionReview.basis_payload_hash != NMVSException.payload_hash
    if work_status == "open":
        statement = statement.where(
            or_(
                ExceptionReview.exception_id.is_(None),
                ExceptionReview.status != "resolved",
                stale,
            )
        )
    elif work_status == "to_do":
        statement = statement.where(ExceptionReview.status == "to_do")
    elif work_status == "resolved":
        statement = statement.where(ExceptionReview.status == "resolved", ~stale)
    if date_quality == "unresolved":
        statement = statement.where(NMVSException.alert_at.is_(None))
    elif work_status != "to_do":
        statement = statement.where(
            NMVSException.alert_at >= datetime.combine(start, datetime.min.time()),
            NMVSException.alert_at
            < datetime.combine(end + timedelta(days=1), datetime.min.time()),
        )
    if intermarket:
        statement = statement.where(
            NMVSException.is_intermarket.is_(None)
            if intermarket == "unset"
            else NMVSException.is_intermarket == int(intermarket == "yes")
        )
    if q:
        statement = statement.where(
            or_(
                *(
                    f.contains(q, autoescape=True)
                    for f in (
                        NMVSException.unique_alert_id,
                        NMVSException.product_code,
                        NMVSException.gtin14,
                        NMVSException.provided_batch,
                        NMVSException.stored_batch,
                        NMVSException.serial_number,
                        NMVSException.transaction_id,
                    )
                )
            )
        )
    for column, value in (
        (NMVSException.error_code, error),
        (NMVSException.source_market, market),
        (NMVSException.organisation_id, organisation),
        (NMVSException.source_location_id, location),
        (NMVSException.business_process, process),
    ):
        if value:
            statement = statement.where(column == value)
    ordering = (
        (
            ExceptionReview.due_date.is_(None),
            ExceptionReview.due_date,
            NMVSException.alert_at,
            NMVSException.id,
        )
        if work_status == "to_do"
        else (NMVSException.alert_at.desc(), NMVSException.id.desc())
    )
    return statement, ordering


def listing(session, *, page=1, **filters):
    statement, ordering = listing_statement(session, **filters)
    rows, pagination = paged(
        session,
        statement.order_by(*ordering),
        page,
    )
    return enriched(session, [r[0] for r in rows]), pagination


def options(session):
    ns = namespace(session)
    return {
        name: session.scalars(
            select(field)
            .where(NMVSException.source_namespace == ns, field.is_not(None))
            .distinct()
            .order_by(field)
        ).all()
        for name, field in [
            ("errors", NMVSException.error_code),
            ("markets", NMVSException.source_market),
            ("processes", NMVSException.business_process),
        ]
    }


def detail(session, record):
    view = enriched(session, [record])[0]
    product = view["product"]
    batches = {}
    if product:
        for which, batch in [
            ("provided_batch", record.provided_batch),
            ("stored_batch", record.stored_batch),
        ]:
            if batch:
                b = session.scalar(
                    select(Batch).where(
                        Batch.batch_key == key(product.source_key, batch),
                        Batch.is_observed == 1,
                    )
                )
                batches[which] = b
    related = []
    if record.product_code_scheme and record.product_code and record.serial_number:
        related = session.scalars(
            select(NMVSException)
            .where(
                NMVSException.source_namespace == record.source_namespace,
                NMVSException.id != record.id,
                NMVSException.product_code_scheme == record.product_code_scheme,
                NMVSException.product_code == record.product_code,
                NMVSException.serial_number == record.serial_number,
            )
            .order_by(NMVSException.alert_at.desc())
            .limit(20)
        ).all()
        # SQL collation may fold case: require exact source spelling before correlating packs.
        related = [
            r
            for r in related
            if (r.product_code_scheme, r.product_code, r.serial_number)
            == (record.product_code_scheme, record.product_code, record.serial_number)
        ]
    revisions = session.scalars(
        select(ExceptionRevision)
        .where(ExceptionRevision.exception_id == record.id)
        .order_by(ExceptionRevision.observed_at.desc(), ExceptionRevision.id.desc())
    ).all()
    return {
        **view,
        "batch_links": batches,
        "related": related,
        "revisions": revisions,
        "source_publication": session.get(
            ExceptionPublication, record.last_publication_id
        ),
    }
