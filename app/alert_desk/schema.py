"""Commands and labels shared by the pilot UI and private service."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

PUBLIC_ORIGIN = "http://localhost:8014"
PRIVATE_ORIGIN = "http://127.0.0.1:8015"
COOKIE = "alert_desk_case"
SESSION_PATH = "/alerts"
GRANT_HOURS = 24

FINDINGS = {
    "procedural": "Process or handling error on my side",
    "technical": "Scanner or software error on my side",
    "other": "Other issue on my side",
    "not_my_side": "Root cause not on my side",
    "investigating": "Still investigating",
}
OWN_SIDE = ("procedural", "technical", "other")
CAPA = {
    "implemented": "Implemented",
    "planned": "Planned",
    "pending": "Not yet planned",
}
COMPARISON = {"yes": "Yes", "no": "No", "not_checked": "Not checked"}


class Capability(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{43}$")]


class Findings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    submission_key: UUID
    publication: int
    basis: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")] | None = None
    batch_revision: (
        Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")] | None
    ) = None
    pack_on_hold: bool = False
    comparison: Literal["yes", "no", "not_checked"] | None = None
    batch_uploaded: Literal["yes", "no"] | None = None
    serial_accepted: Literal["yes", "no"] | None = None
    other_issue: bool = False
    finding: Literal["procedural", "technical", "other", "not_my_side", "investigating"]
    capa: Literal["implemented", "planned", "pending"] | None = None
    comment: Annotated[
        str, StringConstraints(strip_whitespace=True, max_length=1000)
    ] = ""

    @model_validator(mode="after")
    def validate_capa(self):
        if (self.finding in OWN_SIDE) != bool(self.capa):
            raise ValueError("Record CAPA status when reporting an issue on your side.")
        return self

    def matches_audience(self, audience, alert_code="A3"):
        if self.pack_on_hold and (
            audience != "end_user" or alert_code not in {"A2", "A3"}
        ):
            return False
        if self.batch_revision and (alert_code not in {"A2", "A7"} or self.pack_on_hold):
            return False
        if alert_code == "A7":
            return not (
                self.comparison
                or self.batch_uploaded
                or self.serial_accepted
                or self.other_issue
            ) and (
                audience == "end_user"
                or self.finding in {"other", "not_my_side", "investigating"}
            )
        if audience != "mah":
            return bool(
                self.comparison
                and not (
                    self.batch_uploaded or self.serial_accepted or self.other_issue
                )
            )
        if alert_code == "A2":
            return not (self.comparison or self.serial_accepted) and (
                self.finding == "investigating"
                or (
                    self.finding == "other"
                    and (self.other_issue or self.batch_uploaded == "no")
                )
                or (
                    self.finding == "not_my_side"
                    and self.batch_uploaded == "yes"
                    and not self.other_issue
                )
            )
        if self.comparison or (self.serial_accepted and self.batch_uploaded != "yes"):
            return False
        if self.finding == "investigating":
            return True
        if self.finding == "other":
            return self.other_issue or "no" in (
                self.batch_uploaded,
                self.serial_accepted,
            )
        return (
            self.finding == "not_my_side"
            and not self.other_issue
            and self.batch_uploaded == self.serial_accepted == "yes"
        )


class MailboxCode(Capability):
    code: Annotated[str, StringConstraints(pattern=r"^[0-9]{6}$")]
