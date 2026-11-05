"""Local work management; never changes the source Alert or sends a closure."""

from datetime import UTC, datetime

from sqlalchemy import select

from app.domain.models import ExceptionReview, ExceptionReviewEvent, NMVSException

FIELDS = (
    "status",
    "cause",
    "findings",
    "next_action",
    "due_date",
    "review_reason",
    "analysis",
    "resolution",
)


def snapshot(review):
    if not review:
        return {}
    return {
        k: str(getattr(review, k))
        if k == "due_date" and getattr(review, k)
        else getattr(review, k)
        for k in FIELDS
    }


def save(session, record, version, payload_hash, values, origin):
    review = session.get(ExceptionReview, record.id)
    if (
        review.version if review else 0
    ) != version or record.payload_hash != payload_hash:
        raise ValueError(
            "This exception or review changed. Reload the page before saving."
        )
    before = snapshot(review)
    if review:
        before["basis_payload_hash"] = review.basis_payload_hash
    after = {k: str(v) if k == "due_date" and v else v for k, v in values.items()}
    after["basis_payload_hash"] = payload_hash
    if review and before == after and review.basis_payload_hash == payload_hash:
        return
    if not review:
        review = ExceptionReview(exception_id=record.id)
        session.add(review)
    for k, v in values.items():
        setattr(review, k, v)
    review.updated_at = datetime.now(UTC).replace(tzinfo=None)
    review.basis_payload_hash = payload_hash
    session.add(
        ExceptionReviewEvent(
            exception_id=record.id,
            occurred_at=review.updated_at,
            actor="Local operator (no authenticated identity)",
            before=before,
            after=after,
            originating_exception_id=origin,
        )
    )


def signature(record):
    # Provided and stored batch roles must both match; unknown batches are excluded.
    return (
        record.source_namespace,
        record.product_code_scheme,
        record.product_code,
        record.provided_batch,
        record.stored_batch,
        record.error_code,
        record.source_market,
        record.business_process,
        record.is_intermarket,
        record.evidence.get("attemptedOperation"),
    )


def similar(session, record):
    if (
        not record.product_code_scheme
        or not record.product_code
        or not (record.provided_batch or record.stored_batch)
        or not record.error_code
    ):
        return []
    candidates = session.scalars(
        select(NMVSException)
        .where(
            NMVSException.source_namespace == record.source_namespace,
            NMVSException.product_code_scheme == record.product_code_scheme,
            NMVSException.product_code == record.product_code,
            NMVSException.provided_batch == record.provided_batch,
            NMVSException.stored_batch == record.stored_batch,
            NMVSException.error_code == record.error_code,
            NMVSException.id != record.id,
        )
        .order_by(NMVSException.id)
    ).all()
    result = []
    for other in candidates:
        if signature(other) != signature(record):
            continue
        review = session.get(ExceptionReview, other.id)
        if (
            not review
            or review.status != "resolved"
            or review.basis_payload_hash != other.payload_hash
        ):
            result.append((other, review))
        if len(result) == 50:
            break
    return result


def reopen_values(review, record, reason):
    values = {field: getattr(review, field) for field in FIELDS}
    analysis = review.analysis
    if analysis and review.basis_payload_hash != record.payload_hash:
        analysis = {
            **analysis,
            "confidence": "suspected"
            if analysis.get("category") != "unknown"
            else "unassessed",
            "checks": {},
        }
    values.update(
        status="open",
        analysis=analysis,
        resolution={"reopened_reason": reason, "previous": review.resolution},
    )
    return values
