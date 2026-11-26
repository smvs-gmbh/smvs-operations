"""Initial synthetic Alert Desk seed for the verified empty hosted TEST store."""

import secrets

from sqlalchemy import func, select, text

from app.core.config import get_settings
from app.core.db.session import SessionFactory, get_session_factory


def main():
    settings = get_settings()
    if not (settings.environment == "test" and settings.alert_desk_test_enabled):
        raise RuntimeError("Synthetic seeding requires explicitly enabled TEST.")
    with SessionFactory() as session:
        host, database = session.execute(text("SELECT @@hostname, DATABASE()")).one()
        if host.split(".")[0] != "node221861-env-1900268" or database != "smvs_operations":
            raise RuntimeError("Seed refused outside the confirmed TEST store.")
        tables = session.execute(text("SHOW TABLES")).scalars()
        for table in tables:
            if table == "alembic_version":
                continue
            if table == "import_mutexes":
                expected = {
                    "mapping:product-batch", "mapping:participants", "mapping:activity",
                    "mapping:exceptions", "queue:pack-audit", "worker:pack-audit",
                    "queue:uploads", "worker:uploads", "queue:imports-ui",
                }
                actual = set(session.execute(text("SELECT import_key FROM import_mutexes")).scalars())
                if actual != expected:
                    raise RuntimeError("Unexpected TEST migration lock records.")
                continue
            if not table.replace("_", "").isalnum():
                raise RuntimeError("Unexpected table identifier.")
            if session.execute(text("SELECT COUNT(*) FROM `" + table + "`")).scalar():
                raise RuntimeError("Seed refused: TEST already contains records.")
    from app.alert_desk.test_pack_audits import seed_pack_audits
    from app.alert_desk.test_workspace import CODES, NS, seed
    from app.domain.models import AlertDeskAccess, NMVSException, PortalUser

    # Reuse reviewed synthetic content, but retain no pre-authenticated fixture
    # sessions. Hosted users must follow the real invitation/mailbox flow.
    seed(get_session_factory(), {r: secrets.token_urlsafe(32) for r in ("end_user", "mah")})
    with SessionFactory() as session, session.begin():
        for grant in session.scalars(select(AlertDeskAccess)):
            grant.session_hash = None
            grant.session_expires_at = None
            grant.accepted_at = None
            grant.sent_at = None
            grant.revoked_at = grant.invited_at
        user = session.scalar(select(PortalUser))
        user.handle = secrets.token_hex(32)
    seed_pack_audits(SessionFactory, NS, CODES)
    with SessionFactory() as session:
        print("Synthetic TEST alerts:", session.scalar(select(func.count()).select_from(NMVSException)))


if __name__ == "__main__":
    main()
