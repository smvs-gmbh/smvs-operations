import gzip
import hashlib
import io
import json
import subprocess
from types import SimpleNamespace

import pytest

from app.domain.crm import backup


def settings():
    return SimpleNamespace(
        db_name="smvs_operations",
        db_host="localhost",
        db_port=3306,
        db_user="fixture",
        db_password='synthetic-secret " \\ \n',
        db_ssl_ca=None,
    )


def client(monkeypatch, success):
    cfg = settings()

    class Process:
        def __init__(self, args, **kwargs):
            assert cfg.db_password not in " ".join(args)
            from pathlib import Path

            option_file = Path(args[1].split("=", 1)[1])
            assert option_file.stat().st_mode & 0o077 == 0
            assert "password=" in option_file.read_text()
            assert "--single-transaction" in args and "--hex-blob" in args
            self.stdout = io.BytesIO(
                b"-- SQL fixture\nCREATE TABLE fixture(id INT);\nINSERT INTO fixture VALUES (1);\n"
            )
            if not success:
                kwargs["stderr"].write(
                    b"ERROR 1234 credential-bearing diagnostic suppressed"
                )

        def wait(self):
            return 0 if success else 1

        def terminate(self):
            pass

    monkeypatch.setattr(
        backup.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a[0], 0, "mysqldump 8.3.0", ""),
    )
    monkeypatch.setattr(backup.subprocess, "Popen", Process)
    return cfg


def test_backup_has_private_manifest_checksum_and_restorable_gzip_without_credentials(
    tmp_path, monkeypatch
):
    cfg = client(monkeypatch, True)
    folder = backup.backup_database(
        tmp_path / "private", settings=cfg, executable="/fixture/dump"
    )
    metadata = json.loads((folder / "manifest.json").read_text())
    data = (folder / "database.sql.gz").read_bytes()
    assert metadata["status"] == "complete" and not metadata["restore_tested"]
    assert hashlib.sha256(data).hexdigest() == metadata["sha256"]
    assert b"CREATE TABLE fixture" in gzip.decompress(data)
    assert cfg.db_password not in json.dumps(metadata)
    assert (folder / "database.sql.gz").stat().st_mode & 0o077 == 0
    assert (folder / "manifest.json").stat().st_mode & 0o077 == 0


def test_backup_failure_never_produces_completed_manifest_or_partial_dump(
    tmp_path, monkeypatch
):
    cfg = client(monkeypatch, False)
    with pytest.raises(RuntimeError, match="ERROR 1234") as error:
        backup.backup_database(
            tmp_path / "private", settings=cfg, executable="/fixture/dump"
        )
    assert "credential-bearing" not in str(error.value)
    assert not list(tmp_path.rglob("manifest.json"))
    assert not list(tmp_path.rglob("*.partial"))
