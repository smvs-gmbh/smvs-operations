"""Idempotent user-owned Supervisor launcher for startup/cron on the private node."""

import fcntl
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parent
(root / "run").mkdir(mode=0o700, exist_ok=True)
(root / "logs").mkdir(mode=0o700, exist_ok=True)
with (root / "run/start.lock").open("a") as lock:
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(0) from None
    args = ["-c", str(root / "supervisor.conf")]
    running = subprocess.run(
        [str(root / ".venv/bin/supervisorctl"), *args, "pid"],
        capture_output=True,
        check=False,
    )
    if running.returncode:
        subprocess.run(
            [str(root / ".venv/bin/supervisord"), *args], cwd=root, check=True
        )
