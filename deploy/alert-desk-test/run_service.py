"""Run one separately supervised service from a committed TEST release."""

import json
import os
import sys
from pathlib import Path


def main():
    root = Path(os.environ["SMVS_TEST_ROOT"]).resolve()
    path = root / "private/runtime.json"
    if path.stat().st_mode & 0o077 or path.stat().st_uid != os.getuid():
        raise RuntimeError("TEST configuration must be owner-only.")
    config = json.loads(path.read_text())
    if config["ENVIRONMENT"] != "test" or config["DB_NAME"] != "smvs_operations":
        raise RuntimeError("Refuse a non-TEST configuration.")
    role = sys.argv[1]
    if role not in {"portal", "api", "gateway", "mail"}:
        raise RuntimeError("Unknown TEST service.")
    if role in {"gateway", "mail"}:
        # Public-facing gateway and capture SMTP receive no database/source keys.
        allowed = {
            "ENVIRONMENT", "ALERT_DESK_TEST_ENABLED", "ALERT_DESK_PILOT_SECRET",
            "ALERT_DESK_PUBLIC_ORIGIN", "ALERT_DESK_PRIVATE_ORIGIN",
        }
        config = {k: v for k, v in config.items() if k in allowed}
    for name in list(os.environ):
        if name.startswith(("DB_", "NMVS_", "AMS_", "SENDGRID_", "OPENAI_", "ALERT_DESK_SENDGRID_")):
            del os.environ[name]
    os.environ.update(config)
    release = (root / "current").resolve()
    if release.parent != root / "releases":
        raise RuntimeError("TEST release must be an identified archive.")
    os.chdir(release)
    sys.path.insert(0, str(release))
    if role == "mail":
        from app.alert_desk.capture_mail import run

        run(root / "private/mail")
        return
    import uvicorn

    targets = {
        "portal": ("app.main:app", 8016, False),
        "api": ("app.domain.investigations.pilot_api:local_app", 8017, True),
        "gateway": ("app.alert_desk.web:local_app", 8018, True),
    }
    target, port, factory = targets[role]
    uvicorn.run(target, factory=factory, host="127.0.0.1", port=port,
                access_log=False, proxy_headers=False)


if __name__ == "__main__":
    main()
