"""Private, streamed consistent database backups including CRM documents and audit data.

No credentials in argv/log output. A complete manifest is written only after the
compressed dump and its checksum are complete. No automatic deletion/retention.
"""

import argparse
import fcntl
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def option(value):
    return (
        '"'
        + str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        + '"'
    )


def _backup_database(destination, *, settings=None, executable=None):
    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()
    if settings.db_name != "smvs_operations":
        raise ValueError("Backups are enabled only for smvs_operations.")
    executable = executable or shutil.which("mysqldump") or shutil.which("mariadb-dump")
    if not executable and Path("/usr/local/mysql/bin/mysqldump").exists():
        executable = "/usr/local/mysql/bin/mysqldump"
    if not executable:
        raise RuntimeError(
            "Install a compatible mysqldump/mariadb-dump client before running backups."
        )
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    if destination.stat().st_mode & 0o077:
        raise ValueError("Backup destination must be private (chmod 700).")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = destination / ("operations-" + stamp)
    folder.mkdir(mode=0o700)
    dump = folder / "database.sql.gz"
    partial = folder / "database.sql.gz.partial"
    version = subprocess.run(
        [str(executable), "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    maria = "mariadb" in version.lower()
    with tempfile.TemporaryDirectory(prefix="smvs-backup-") as private:
        config = Path(private) / "client.cnf"
        values = {
            "host": settings.db_host,
            "port": settings.db_port,
            "user": settings.db_user,
            "password": settings.db_password,
            "default-character-set": "utf8mb4",
        }
        if getattr(settings, "db_socket", None):
            values.pop("host")
            values.pop("port")
            values.update(socket=settings.db_socket, protocol="SOCKET")
        if settings.db_ssl_ca:
            values["ssl-ca"] = settings.db_ssl_ca
        config.write_text(
            "[client]\n"
            + "".join(key + "=" + option(value) + "\n" for key, value in values.items())
        )
        config.chmod(0o600)
        args = [
            str(executable),
            "--defaults-extra-file=" + str(config),
            "--single-transaction",
            "--quick",
            "--hex-blob",
            "--skip-lock-tables",
            "--no-tablespaces",
            "--routines",
            "--events",
            "--triggers",
        ]
        if not maria:
            args += ["--set-gtid-purged=OFF", "--column-statistics=0"]
            if settings.db_ssl_ca:
                args += ["--ssl-mode=VERIFY_CA"]
        args.append(settings.db_name)
        try:
            with tempfile.TemporaryFile() as errors, partial.open("xb") as output:
                os.chmod(partial, 0o600)
                process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=errors)
                try:
                    with gzip.GzipFile(
                        fileobj=output, mode="wb", mtime=0
                    ) as compressed:
                        shutil.copyfileobj(
                            process.stdout, compressed, length=1024 * 1024
                        )
                except BaseException:
                    process.terminate()
                    process.wait()
                    raise
                finally:
                    process.stdout.close()
                code = process.wait()
                if code:
                    errors.seek(0)
                    error = re.search(rb"ERROR\s+\d+", errors.read(65536))
                    raise RuntimeError(
                        "Database backup failed"
                        + (" (" + error[0].decode() + ")" if error else "")
                        + "; no completed backup was recorded."
                    )
                output.flush()
                os.fsync(output.fileno())
            if partial.stat().st_size < 32:
                raise RuntimeError(
                    "Database backup was empty; no completed backup was recorded."
                )
            partial.replace(dump)
            with dump.open("rb") as verified:
                digest = hashlib.file_digest(verified, "sha256").hexdigest()
            manifest = {
                "status": "complete",
                "created_at_utc": stamp,
                "database": settings.db_name,
                "dump": dump.name,
                "bytes": dump.stat().st_size,
                "sha256": digest,
                "client": version,
                "scope": "Entire database: tables, rows, blobs/documents, triggers, routines and events. Application/configuration files are backed up separately.",
                "restore_tested": False,
            }
            manifest_file = folder / "manifest.json.partial"
            manifest_file.write_text(json.dumps(manifest, indent=2) + "\n")
            manifest_file.chmod(0o600)
            manifest_file.replace(folder / "manifest.json")
            return folder
        except BaseException:
            partial.unlink(missing_ok=True)
            raise


def backup_database(destination, *, settings=None, executable=None):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    if destination.stat().st_mode & 0o077:
        raise ValueError("Backup destination must be private (chmod 700).")
    with (destination / ".backup.lock").open("a") as lock:
        os.chmod(lock.name, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(
                "A database backup is already running for this destination."
            ) from None
        return _backup_database(destination, settings=settings, executable=executable)


def main():
    parser = argparse.ArgumentParser(
        description="Create a private consistent compressed database backup. No automatic deletion."
    )
    parser.add_argument("destination", type=Path)
    parser.add_argument("--dump-client", type=Path)
    parser.add_argument(
        "--settings-file",
        type=Path,
        help="Optional private JSON configuration for a standalone database-node job.",
    )
    args = parser.parse_args()
    try:
        settings = None
        if args.settings_file:
            from types import SimpleNamespace

            if args.settings_file.stat().st_mode & 0o077:
                raise ValueError("Backup settings must be private (chmod 600).")
            data = json.loads(args.settings_file.read_text())
            allowed = {
                "db_name",
                "db_host",
                "db_port",
                "db_user",
                "db_password",
                "db_socket",
                "db_ssl_ca",
            }
            if not isinstance(data, dict) or set(data) - allowed:
                raise ValueError("Invalid private backup settings.")
            settings = SimpleNamespace(
                db_host="localhost",
                db_port=3306,
                db_ssl_ca=None,
                **{
                    k: v
                    for k, v in data.items()
                    if k not in {"db_host", "db_port", "db_ssl_ca"}
                },
            )
            for key in ("db_host", "db_port", "db_ssl_ca"):
                if key in data:
                    setattr(settings, key, data[key])
        folder = backup_database(
            args.destination, settings=settings, executable=args.dump_client
        )
    except Exception as error:  # noqa: BLE001 -- suppress credential-bearing driver/client diagnostics
        # Dump errors are deliberately sanitised; never print Settings or connection URLs.
        if isinstance(error, (ValueError, RuntimeError)):
            parser.exit(1, str(error) + "\n")
        parser.exit(
            1,
            "Backup failed; no completed backup was confirmed. Check private directory/client access.\n",
        )
    print(
        json.dumps(
            {"backup": str(folder), "status": "complete", "restore_tested": False}
        )
    )


if __name__ == "__main__":
    main()
