from datetime import UTC, datetime

from app.integration.sources.nmvs.pack_audit.api import PackAuditClient
from app.integration.sources.nmvs.reporting import ReportingApiError
from app.integration.sources.nmvs.uploads.parsing import instant


class UploadClient(PackAuditClient):
    report_type = "ProductPackUploadAuditTrailReport"
    required_parameters = frozenset({"startDateTime", "endDateTime"})

    def get_upload(self, start, end, *, title, created_at):
        definition = self.definition()
        # Never claim coverage of a period that the source has not yet completed.
        if end > instant(definition["latestAvailableData"]) or end > datetime.now(
            UTC
        ).replace(tzinfo=None):
            raise ReportingApiError(
                "Upload source has not completed the requested period."
            )
        params = {p.get("id"): p for p in definition.get("parameters", [])}
        if params.get("syntheticMonitoring", {}).get("type") != "bool":
            raise ReportingApiError(
                "Upload API version does not support the genuine filter."
            )
        return self.get_pack(
            {
                "startDateTime": start.isoformat() + "Z",
                "endDateTime": end.isoformat() + "Z",
                # Confirmed in Reporting API 3.6; validate the resulting CSV too.
                "syntheticMonitoring": False,
            },
            title=title,
            created_at=created_at,
        )
