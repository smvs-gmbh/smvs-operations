import hashlib
import ssl
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.db.engine import tls_configuration, verify_database_tls
from app.core.db.safety import DatabaseSafetyError


def test_local_database_remains_unconfigured_for_tls():
    assert tls_configuration(SimpleNamespace()) == ({}, None)


@pytest.mark.parametrize("ca,pin", [(None, "a" * 64), ("ca.pem", "invalid")])
def test_pin_cannot_disable_trust_without_a_valid_ca_and_digest(ca, pin):
    with pytest.raises(DatabaseSafetyError):
        tls_configuration(SimpleNamespace(db_ssl_ca=ca, db_ssl_server_cert_sha256=pin))


def test_verified_ca_and_hostname_are_default(monkeypatch):
    context = ssl.create_default_context()
    monkeypatch.setattr(
        "app.core.db.engine.ssl.create_default_context", lambda **kwargs: context
    )
    result, pin = tls_configuration(
        SimpleNamespace(db_ssl_ca="trusted-ca.pem", db_ssl_server_cert_sha256=None)
    )
    assert result["ssl"] is context and context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname and pin is None


def test_pin_checks_exact_server_identity_and_does_not_disable_ca_verification(
    monkeypatch,
):
    context = ssl.create_default_context()
    monkeypatch.setattr(
        "app.core.db.engine.ssl.create_default_context", lambda **kwargs: context
    )
    leaf = b"synthetic server certificate"
    fingerprint = hashlib.sha256(leaf).hexdigest()
    result, pin = tls_configuration(
        SimpleNamespace(
            db_ssl_ca="trusted-ca.pem", db_ssl_server_cert_sha256=fingerprint.upper()
        )
    )
    assert result["ssl"].verify_mode == ssl.CERT_REQUIRED and not context.check_hostname
    assert pin == fingerprint
    socket = Mock(spec=ssl.SSLSocket)
    socket.getpeercert.return_value = leaf
    verify_database_tls(SimpleNamespace(_sock=socket), pin)
    with pytest.raises(DatabaseSafetyError):
        verify_database_tls(SimpleNamespace(_sock=socket), "0" * 64)
    with pytest.raises(DatabaseSafetyError):
        verify_database_tls(SimpleNamespace(_sock=object()), pin)


def test_legacy_format_requires_pin_and_keeps_ca_signature_verification(monkeypatch):
    with pytest.raises(DatabaseSafetyError):
        tls_configuration(
            SimpleNamespace(db_ssl_ca="ca.pem", db_ssl_legacy_certificate=True)
        )
    context = ssl.create_default_context()
    monkeypatch.setattr(
        "app.core.db.engine.ssl.create_default_context", lambda **kwargs: context
    )
    result, pin = tls_configuration(
        SimpleNamespace(
            db_ssl_ca="ca.pem",
            db_ssl_server_cert_sha256="a" * 64,
            db_ssl_legacy_certificate=True,
        )
    )
    assert result["ssl"].verify_mode == ssl.CERT_REQUIRED
    assert not (context.verify_flags & ssl.VERIFY_X509_STRICT)
    assert pin == "a" * 64
