from __future__ import annotations

import hashlib
import hmac
import re
import ssl

from sqlalchemy import URL, create_engine, event, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings
from app.core.db.safety import (
    DatabaseSafetyError,
    assert_configured_database_safe,
    assert_migration_database_safe,
)


def build_database_url() -> URL:
    settings = get_settings()
    assert_configured_database_safe(settings.db_name)
    return URL.create(
        drivername="mysql+pymysql",
        username=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
    )


def tls_configuration(settings):
    ca = getattr(settings, "db_ssl_ca", None)
    pin = getattr(settings, "db_ssl_server_cert_sha256", None)
    if pin and (not ca or not re.fullmatch(r"[0-9a-fA-F]{64}", pin)):
        raise DatabaseSafetyError(
            "A database certificate pin requires a trusted CA and SHA-256 fingerprint."
        )
    legacy = getattr(settings, "db_ssl_legacy_certificate", False)
    if legacy and not (ca and pin):
        raise DatabaseSafetyError(
            "Legacy certificate compatibility requires a trusted CA and exact server pin."
        )
    if not ca:
        return {}, None
    context = ssl.create_default_context(cafile=ca)
    if pin:
        # MySQL's auto-generated certificate has no host SAN. Its identity is
        # verified by a separate exact leaf-certificate pin, never trust-all TLS.
        context.check_hostname = False
    if legacy:
        # MySQL-generated certificates lack AKI/SKI extensions. Only this explicit
        # pinned-server mode allows their older format; CA/signature/expiry and
        # exact server identity checks remain mandatory.
        context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return {"ssl": context}, pin.lower() if pin else None


def verify_database_tls(connection, pin=None):
    sock = getattr(connection, "_sock", None)
    if not isinstance(sock, ssl.SSLSocket):
        raise DatabaseSafetyError("An encrypted database connection is required.")
    if pin:
        certificate = sock.getpeercert(binary_form=True)
        if not certificate or not hmac.compare_digest(
            hashlib.sha256(certificate).hexdigest(), pin
        ):
            raise DatabaseSafetyError(
                "The database certificate does not match its configured identity."
            )


def create_database_engine() -> Engine:
    connect_args, pin = tls_configuration(get_settings())
    engine = create_engine(
        build_database_url(), pool_pre_ping=True, connect_args=connect_args
    )
    if connect_args:

        @event.listens_for(engine, "connect")
        def encrypted_connection(connection, _):
            verify_database_tls(connection, pin)

    return engine


def assert_engine_database_safe(engine: Engine) -> None:
    settings = get_settings()
    assert_configured_database_safe(settings.db_name)
    with engine.connect() as connection:
        selected_name = connection.execute(
            text("SELECT DATABASE()")
        ).scalar_one_or_none()
    assert_migration_database_safe(settings.db_name, lambda: selected_name)
