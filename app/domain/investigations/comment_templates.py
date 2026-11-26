"""Personal templates: verified contact + role/organisation, never case tokens."""

from hashlib import sha256
from typing import Annotated, Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import StaleDataError

from app.domain.investigations import pilot
from app.domain.models import AlertDeskCommentTemplate as Template
from app.domain.models import AlertDeskCommentTemplateEvent as Event


class TemplateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command: Literal["create", "update", "delete", "insert"]
    template_id: int | None = Field(None, ge=1)
    version: int | None = Field(None, ge=1)
    name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)] = ""
    text: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] = ""

    @model_validator(mode="after")
    def complete(self):
        if self.command in {"create", "update"} and not (self.name and self.text):
            raise ValueError("Enter a template name and text.")
        if self.command != "create" and not (self.template_id and self.version):
            raise ValueError("Choose a current template.")
        if self.command == "create" and (
            self.template_id is not None or self.version is not None
        ):
            raise ValueError("A new template cannot specify an existing identity.")
        return self


def owned(grant):
    return select(Template).where(
        Template.contact_id == grant.contact_id,
        Template.role == grant.role,
        Template.crm_organisation_id == grant.crm_organisation_id,
        Template.deleted_at.is_(None),
    )


def serialise(row, *, detail=False):
    return {
        "id": row.id,
        "name": row.name,
        "version": row.version,
        "updated_at": row.updated_at.isoformat() + "Z",
        **({"text": row.text} if detail else {}),
    }


def get_owned(session, grant, identifier):
    row = session.scalar(owned(grant).where(Template.id == identifier))
    if row is None:
        raise HTTPException(404, "Template unavailable.")
    return row


def install(app, sessions, capability, active, current_case):
    @app.get("/access/alerts/{identifier}/comment-templates")
    def listing(identifier: int, token: Annotated[str, Depends(capability)]):
        with sessions() as session:
            grant, crm = active(session, token)
            current_case(session, grant, crm, identifier)
            return {
                "templates": [
                    serialise(row)
                    for row in session.scalars(
                        owned(grant).order_by(Template.name, Template.id).limit(50)
                    )
                ]
            }

    @app.get("/access/alerts/{identifier}/comment-templates/{template_id}")
    def detail(
        identifier: int, template_id: int, token: Annotated[str, Depends(capability)]
    ):
        with sessions() as session:
            grant, crm = active(session, token)
            current_case(session, grant, crm, identifier)
            return {
                "template": serialise(
                    get_owned(session, grant, template_id), detail=True
                )
            }

    @app.post("/access/alerts/{identifier}/comment-templates")
    def command(
        identifier: int,
        body: TemplateCommand,
        token: Annotated[str, Depends(capability)],
    ):
        try:
            with sessions() as session, session.begin():
                # Serialise quota/name changes for one stable access scope.
                grant, crm = active(session, token, lock=True)
                current_case(session, grant, crm, identifier)
                before = None
                if body.command == "create":
                    count = session.scalar(
                        owned(grant).with_only_columns(
                            func.count(), maintain_column_froms=True
                        )
                    )
                    if count >= 50:
                        raise HTTPException(422, "Keep at most 50 personal templates.")
                    row = Template(
                        contact_id=grant.contact_id,
                        role=grant.role,
                        crm_organisation_id=grant.crm_organisation_id,
                        created_at=pilot.now(),
                        updated_at=pilot.now(),
                    )
                    session.add(row)
                else:
                    row = get_owned(session, grant, body.template_id)
                    if row.version != body.version:
                        raise HTTPException(
                            409, "This template changed. Reload the list."
                        )
                    before = serialise(row, detail=True)
                if body.command in {"create", "update"}:
                    row.name, row.text = body.name, body.text
                    row.name_key = sha256(
                        " ".join(body.name.casefold().split()).encode()
                    ).hexdigest()
                    row.updated_at = pilot.now()
                elif body.command == "delete":
                    row.deleted_at = row.updated_at = pilot.now()
                    row.name_key = None
                session.flush()
                after = serialise(row, detail=True)
                session.add(
                    Event(
                        template_id=row.id,
                        access_id=grant.id,
                        exception_id=identifier,
                        action=body.command,
                        occurred_at=pilot.now(),
                        data={"before": before, "after": after},
                    )
                )
                # The event and mutation commit together, including insert receipts.
                result = (
                    {"template": after}
                    if body.command != "delete"
                    else {"deleted": True}
                )
            return result
        except (IntegrityError, StaleDataError):
            raise HTTPException(
                409, "The template changed or its name is already in use."
            ) from None

    return listing, detail, command
