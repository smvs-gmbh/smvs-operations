from sqlalchemy import case, func, or_, select

from app.core.db.models import StagingDataset, StagingRow
from app.domain.models import (
    Batch,
    CurrentPublication,
    MappingRun,
    Product,
    ProductReferenceMatch,
    ProductSourceRecord,
    ProductVersion,
    SAIHolder,
    SAIPackage,
    SAIPreparation,
)

STATUS_LABELS = {
    "matched_sai": "Matched to SAI",
    "no_sai_match": "No SAI match",
    "not_gtin_matchable": "No GTIN match",
    "ambiguous": "Ambiguous",
}
PAGE_SIZE = 40


def context(session):
    publication = session.get(CurrentPublication, "product-batch")
    if publication is None:
        return {"publication": None, "statistics": {}, "status_labels": STATUS_LABELS}
    run = session.get(MappingRun, publication.mapping_run_id)
    return {
        "publication": publication,
        "statistics": run.statistics or {},
        "status_labels": STATUS_LABELS,
    }


def base_query(publication):
    return (
        select(
            ProductSourceRecord,
            Product,
            ProductReferenceMatch,
            SAIPackage,
            SAIPreparation,
            SAIHolder,
        )
        .join(Product, ProductSourceRecord.product_id == Product.id)
        .outerjoin(
            ProductReferenceMatch, ProductReferenceMatch.product_id == Product.id
        )
        .outerjoin(SAIPackage, ProductReferenceMatch.sai_package_id == SAIPackage.id)
        .outerjoin(SAIPreparation, SAIPackage.preparation_id == SAIPreparation.id)
        .outerjoin(SAIHolder, SAIPreparation.holder_id == SAIHolder.id)
        .where(
            ProductSourceRecord.source_namespace == publication.source_namespace,
            ProductSourceRecord.is_observed == 1,
            ProductSourceRecord.last_mapping_run_id == publication.mapping_run_id,
        )
    )


def search_clause(q, *, batches=False):
    fields = [
        Product.gtin14,
        ProductSourceRecord.source_code,
        SAIPreparation.preparation_name,
        SAIPackage.description_de,
        SAIPackage.description_fr,
        SAIHolder.company_name,
    ]
    if batches:
        fields.append(Batch.batch_code)
    return or_(*(field.contains(q, autoescape=True) for field in fields))


def product_view(row):
    source, product, match, package, preparation, holder = row[:6]
    # Swiss-facing names never fall back to the source's incorrect NMVS labels.
    status = match.match_status if match else "not_gtin_matchable"
    return {
        "id": source.id,
        "gtin14": product.gtin14,
        "source_code": source.source_code,
        "code_scheme": source.code_scheme,
        "name": preparation.preparation_name if preparation else None,
        "description_de": package.description_de if package else None,
        "description_fr": package.description_fr if package else None,
        "holder": holder.company_name if holder else None,
        "approval_number": preparation.approval_number if preparation else None,
        "approval_status": package.approval_status if package else None,
        "atc": preparation.atc_code if preparation else None,
        "version": source.reported_version,
        "version_text": source.reported_version_text,
        "state": source.product_state,
        "pack_count": source.pack_count,
        "active_pack_count": source.active_pack_count,
        "match_status": status,
        "match_label": STATUS_LABELS[status],
    }


def paged(session, statement, page, *, view_request=None, table_key=None):
    if view_request is not None and table_key:
        from app.portal.table_views import apply_sql
        statement = apply_sql(view_request, session, statement, table_key)
    total = session.scalar(
        select(func.count()).select_from(statement.order_by(None).subquery())
    )
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, pages)
    rows = session.execute(
        statement.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    ).all()
    return rows, {
        "page": page,
        "pages": pages,
        "total": total,
        "first": (page - 1) * PAGE_SIZE + 1 if total else 0,
        "last": min(page * PAGE_SIZE, total),
    }


PRODUCT_ORDER = (
    case((ProductReferenceMatch.match_status == "matched_sai", 0), else_=1),
    SAIPreparation.preparation_name,
    Product.gtin14,
    ProductSourceRecord.source_code,
    ProductSourceRecord.id,
)
BATCH_ORDER = (Product.gtin14, Batch.batch_code, Batch.id)


def product_statement(publication, *, q="", status="", version=""):
    statement = base_query(publication)
    if q:
        statement = statement.where(search_clause(q))
    if status:
        statement = statement.where(ProductReferenceMatch.match_status == status)
    if version:
        statement = statement.where(
            ProductSourceRecord.reported_version_text == version
        )
    return statement


def products(session, publication, *, q="", status="", version="", page=1, view_request=None):
    statement = product_statement(publication, q=q, status=status, version=version)
    rows, pagination = paged(session, statement.order_by(*PRODUCT_ORDER), page, view_request=view_request, table_key="products")
    return [product_view(r) for r in rows], pagination


def batch_states(session, publication):
    return session.scalars(
        select(Batch.batch_state)
        .join(ProductSourceRecord, Batch.product_source_id == ProductSourceRecord.id)
        .where(
            ProductSourceRecord.source_namespace == publication.source_namespace,
            ProductSourceRecord.is_observed == 1,
            ProductSourceRecord.last_mapping_run_id == publication.mapping_run_id,
            Batch.is_observed == 1,
            Batch.last_mapping_run_id == publication.mapping_run_id,
            Batch.batch_state.is_not(None),
            Batch.batch_state != "",
        )
        .distinct()
        .order_by(Batch.batch_state)
    ).all()


def batch_statement(publication, *, q="", source_id=None, version="", state=""):
    statement = (
        base_query(publication)
        .add_columns(Batch, ProductVersion)
        .join(Batch, Batch.product_source_id == ProductSourceRecord.id)
        .join(ProductVersion, Batch.product_version_id == ProductVersion.id)
        .where(
            Batch.is_observed == 1,
            Batch.last_mapping_run_id == publication.mapping_run_id,
        )
    )
    if state == "not_expired":
        statement = statement.where(
            or_(Batch.batch_state.is_(None), Batch.batch_state != "Expired")
        )
    elif state:
        statement = statement.where(Batch.batch_state == state)
    if source_id is not None:
        statement = statement.where(ProductSourceRecord.id == source_id)
    if version:
        statement = statement.where(
            Batch.evidence["Product Version Number"].as_string() == version
        )
    if q:
        statement = statement.where(search_clause(q, batches=True))
    return statement


def batches(
    session, publication, *, q="", source_id=None, version="", state="", page=1, view_request=None, table_key="batches"
):
    statement = batch_statement(
        publication, q=q, source_id=source_id, version=version, state=state
    )
    rows, pagination = paged(session, statement.order_by(*BATCH_ORDER), page, view_request=view_request, table_key=table_key)
    output = []
    for row in rows:
        batch, version = row[6:8]
        output.append(
            {
                "id": batch.id,
                "product": product_view(row),
                "code": batch.batch_code,
                "expiry_text": batch.expiry_source_text,
                "state": batch.batch_state,
                "version": version.version_number,
                "version_text": batch.evidence.get(
                    "Product Version Number", version.source_version_value
                ),
                "version_status": version.detail_status,
                "pack_count": batch.pack_count,
                "active_pack_count": batch.active_pack_count,
            }
        )
    return output, pagination


def original_values(session, source, *, kind):
    """Prefer the actual retained staging row; full copied evidence survives expiry."""
    staging = (
        session.get(StagingRow, source.source_row_id) if source.source_row_id else None
    )
    if staging is not None:
        dataset = session.get(StagingDataset, staging.staging_dataset_id)
        raw = staging.raw_row_json
        headers = dataset.source_headers
        complete = True
    else:
        raw = source.evidence
        headers = list(raw)
        # Mapping v2 retains the entire Product row. Legacy v1 evidence is a subset.
        mapping = session.get(MappingRun, source.last_mapping_run_id)
        complete = mapping.mapping_version == "product-batch-sai-2"
    fields = [(name, raw.get(name)) for name in headers]
    fields.extend((name, value) for name, value in raw.items() if name not in headers)
    return {
        "source_fields": fields,
        "source_complete": complete,
        "source_available": staging is not None,
        "source_kind": kind,
    }
