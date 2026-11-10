"""Narrow SQL bootstrap over SSH. Secrets travel on stdin, never in argv/output."""

import argparse
import json
import re
import secrets
import shlex
import subprocess
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
REMOTE = r"""
import json, sys, tempfile, subprocess, re
from pathlib import Path
x=json.load(sys.stdin)
def option(value):
 return '"'+value.replace('\\','\\\\').replace('"','\\"').replace('\n','\\n').replace('\r','\\r')+'"'
with tempfile.TemporaryDirectory(prefix='smvs-db-admin-') as directory:
 config=Path(directory)/'client.cnf'
 config.write_text('[client]\nuser='+option(x['user'])+'\npassword='+option(x['password'])+'\nprotocol=SOCKET\nsocket=/var/lib/mysql/mysql.sock\n')
 config.chmod(0o600)
 result=subprocess.run(['mysql','--defaults-extra-file='+str(config),'--batch','--skip-column-names'],input=x['sql'],capture_output=True,text=True)
 if result.returncode:
  code=re.search(r'ERROR \d+ \([A-Z0-9]+\)',result.stderr)
  print('MySQL operation failed: '+(code.group(0) if code else 'details suppressed to protect credentials'))
  sys.exit(1)
 print(result.stdout, end='')
"""


def query(sql):
    cfg = dotenv_values(ROOT / ".env.mysql-bootstrap")
    if not cfg.get("MYSQL_ADMIN_PASSWORD") or not cfg.get("MYSQL_ADMIN_USER"):
        raise ValueError("Configure the private .env.mysql-bootstrap file.")
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-o",
        "ConnectTimeout=8",
        "-p",
        "3022",
        "220544-9004@gate.jpc.infomaniak.com",
        "python3 -c " + shlex.quote(REMOTE),
    ]
    result = subprocess.run(
        command,
        input=json.dumps(
            {
                "user": cfg["MYSQL_ADMIN_USER"],
                "password": cfg["MYSQL_ADMIN_PASSWORD"],
                "sql": sql,
            }
        ),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            result.stdout.strip()
            or "Database SSH operation failed; credentials were not printed."
        )
    return result.stdout.strip()


def provision():
    target = ROOT / ".env.mysql-runtime"
    if target.exists():
        raise ValueError(
            "A runtime configuration already exists; inspect before provisioning again."
        )
    account_count = query(
        "SELECT COUNT(*) FROM mysql.user WHERE User='smvs_ops_app' AND Host='10.100.32.195';"
    )
    if account_count != "0":
        raise ValueError(
            "The runtime account already exists; no credentials or privileges changed."
        )
    password = secrets.token_urlsafe(48)
    # Persist before CREATE USER, so an interrupted response never loses the credential.
    with open(
        target, "x", opener=lambda path, flags: __import__("os").open(path, flags, 0o600)
    ) as f:
        f.write(
            "DB_HOST=10.100.36.111\nDB_PORT=3306\nDB_NAME=smvs_operations\nDB_USER=smvs_ops_app\nDB_PASSWORD="
            + password
            + "\n"
        )
    assert re.fullmatch(r"[A-Za-z0-9_-]+", password)
    query(
        "CREATE DATABASE IF NOT EXISTS smvs_operations CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;\nCREATE USER 'smvs_ops_app'@'10.100.32.195' IDENTIFIED BY '"
        + password
        + "' REQUIRE SSL;\nGRANT SELECT, INSERT, UPDATE, DELETE ON smvs_operations.* TO 'smvs_ops_app'@'10.100.32.195';"
    )
    print(query("SHOW GRANTS FOR 'smvs_ops_app'@'10.100.32.195';"))
    print(
        "Runtime account provisioned; password stored only in private .env.mysql-runtime."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provision", action="store_true")
    args = parser.parse_args()
    if args.provision:
        provision()
    else:
        print(
            query(
                "SELECT VERSION(),CURRENT_USER(); SHOW DATABASES; SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='smvs_operations';"
            )
        )
