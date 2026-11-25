"""Explicit snapshot fields shared by rendering and server-side saved views.

Swiss product and MAH names remain SAI-owned. Source names stay in NMVS original.
Append fields to preserve the positional keys of existing personal views.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SnapshotField:
    key: str
    label: str
    source_header: str = ""
    attribute: str = ""
    kind: str = "text"

    def expression(self, model):
        if self.attribute:
            return getattr(model, self.attribute)
        return model.evidence[self.source_header].as_string()

    def value(self, record):
        if self.attribute:
            return getattr(record, self.attribute)
        return record.evidence.get(self.source_header)


OBP_FIELDS = (
    SnapshotField("obp_name", "OBP name · NMVS", "OBP Name"),
    SnapshotField("obp_id", "OBP ID · NMVS", "OBP Id"),
)
PRODUCT_FIELDS = (
    SnapshotField("pack_count", "Packs · NMVS", attribute="pack_count", kind="number"),
    SnapshotField("active_pack_count", "Active packs · NMVS", attribute="active_pack_count", kind="number"),
    SnapshotField("state", "Product state · NMVS", attribute="product_state"),
    *OBP_FIELDS,
    SnapshotField("emvs_mah_id", "EMVS MAH ID · NMVS", "EMVS MAH Id"),
    SnapshotField("source_code", "Product code · NMVS", attribute="source_code"),
    SnapshotField("code_scheme", "Product code scheme · NMVS", attribute="code_scheme"),
    SnapshotField("creation_date", "Creation date · NMVS source value", "Creation Date"),
    SnapshotField("withdrawal_date", "Withdrawal date · NMVS source value", "Withdrawal Date"),
    SnapshotField("withdrawal_reason", "Withdrawal reason · NMVS", "Withdrawal Reason"),
    SnapshotField("national_code", "National code · NMVS", "National Code"),
    SnapshotField("article_57_code", "Article 57 code · NMVS", "Article 57 Code"),
)
BATCH_FIELDS = (
    SnapshotField("manufacturer", "Manufacturer · NMVS", "Manufacturer Name"),
    SnapshotField("markets", "Markets · NMVS", "Markets"),
    SnapshotField("creation_date", "Creation date · NMVS source value", "Creation Date"),
    SnapshotField("multimarket", "Is multimarket · NMVS source value", "Is Multimarket"),
    SnapshotField("recall_date", "Recall date · NMVS source value", "Recall Date"),
    SnapshotField("recall_reason", "Recall reason · NMVS", "Recall Reason"),
)


def values(record, fields):
    return {field.key: field.value(record) for field in fields}
