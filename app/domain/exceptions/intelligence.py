"""Versioned scope and deterministic evidence evaluation for the A7 rule."""

from dataclasses import dataclass

from sqlalchemy import select

from app.domain.exceptions import repeat_evidence
from app.domain.models import IntelligenceRuleRevision

RULE_ID = "A7-repeat-operation"
EVALUATOR_VERSION = 1


@dataclass(frozen=True)
class RuleScope:
    version: int = 1
    operation: str = ""
    market: str = ""


def current_scope(session, namespace):
    revision = session.scalar(
        select(IntelligenceRuleRevision)
        .where(IntelligenceRuleRevision.source_namespace == namespace)
        .order_by(IntelligenceRuleRevision.version.desc())
        .limit(1)
    )
    if revision:
        return RuleScope(revision.version, revision.operation, revision.market)
    return RuleScope()


def evaluate(session, record, scope):
    operation = record.evidence.get("attemptedOperation")
    if not repeat_evidence.operation_for(record):
        return None, "Alert type or operation is outside the catalogue."
    if (scope.operation and scope.operation != operation) or (
        scope.market and scope.market != record.source_market
    ):
        return None, "Outside the configured rule scope."
    sequence = repeat_evidence.repeat_sequence(session, record)
    if not sequence:
        return (
            None,
            "The retained audit trail does not establish a same-location repeat.",
        )
    return (
        sequence,
        "Same pack, operation, state and location are supported by the audit trail.",
    )


def can_resolve(review):
    return not review or not (
        review.status in ("resolved", "to_do")
        or review.next_action.strip()
        or review.due_date
    )
