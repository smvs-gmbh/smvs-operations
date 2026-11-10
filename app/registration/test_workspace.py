"""Disposable internal registration review; no Tally or SendGrid requests are made.

Run: python -m app.registration.test_workspace
Open http://localhost:8014/workflows/registrations; restart to reset all fixtures.
"""

import uuid
from datetime import timedelta
from types import SimpleNamespace

from cryptography.fernet import Fernet

from app.domain.crm.registrations import act, import_intake
from app.portal import test_workspace as workspace
from app.portal.registration_routes import router
from app.registration.schema import FIELDS
from app.registration.service import now


def main():
    original_seed = workspace.seed
    original_access = workspace.install_portal_access
    key = Fernet.generate_key().decode()

    def seed(factory):
        original_seed(factory)
        from app.domain.models import PortalUser

        with factory.begin() as session:
            session.add(
                PortalUser(
                    id=0,
                    email="fixture-reviewer@example.test",
                    handle="registration-fixture",
                    is_nmvo=1,
                    is_admin=0,
                )
            )
        with factory.begin() as session:
            for index, confirmed in ((1, False), (2, True), (3, True)):
                values = {k: "Synthetic example" for k in FIELDS}
                values.update(
                    name=f"Registration Test Pharmacy {index}",
                    gln=f"760100130125{index}",
                    first_name="Fixture",
                    last_name=f"Contact {index}",
                    email=f"contact{index}@example.test",
                    country="Schweiz",
                    terms_accepted=True,
                    security_answer="Synthetic answer — never a real credential",
                )
                row = import_intake(
                    session,
                    {
                        "id": str(
                            uuid.uuid5(
                                uuid.NAMESPACE_URL,
                                "smvs-registration-test-" + str(index),
                            )
                        ),
                        "revision": 1,
                        "submitted_at": now().isoformat() + "Z",
                        "confirmed_at": now().isoformat() + "Z" if confirmed else None,
                        "expires_at": (now() + timedelta(days=7)).isoformat() + "Z",
                        "values": values,
                        "mail_status": "accepted",
                    },
                    key,
                )
                if index == 3:
                    act(
                        session,
                        row,
                        "approve",
                        "Fixture reviewer",
                        note="Synthetic registration checked",
                    )

    def access(app, settings):
        original_access(app, settings)
        app.include_router(router)
        from app.portal.table_views import router as views

        app.include_router(views)

        @app.middleware("http")
        async def identity(request, call_next):
            request.state.portal_user = SimpleNamespace(
                id=0, email="fixture-reviewer@example.test", is_nmvo=True
            )
            return await call_next(request)

    from app.core.config import get_settings
    from app.portal import registration_routes

    settings = get_settings().model_copy(
        update={"registration_intake_url": None, "registration_encryption_key": key}
    )
    from pydantic import SecretStr

    settings.registration_encryption_key = SecretStr(key)
    registration_routes.get_settings = lambda: settings
    workspace.seed = seed
    workspace.install_portal_access = access
    workspace.PORT = 8014
    workspace.main()


if __name__ == "__main__":
    main()
