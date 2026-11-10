"""Package only stateless Connect code; no core app, models, DB drivers or secrets."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "app/__init__.py",
    "app/connect/__init__.py",
    "app/connect/gateway.py",
    "app/connect/settings.py",
    "app/connect/protocol.py",
    "app/registration/__init__.py",
    "app/registration/schema.py",
    "app/registration/templates/confirm.html",
    "app/registration/templates/home.html",
    "app/registration/templates/confirmation.js",
    "app/registration/templates/confirmation.css",
)


def package(output):
    files = {name: (ROOT / name).read_bytes() for name in FILES}
    for name in ("requirements.txt", "README.md", "start-connect.sh"):
        files[name] = (ROOT / "deploy/connect" / name).read_bytes()
    files["connect.env.example"] = (ROOT / "config/connect.env.example").read_bytes()
    manifest = {
        name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())
    }
    files["MANIFEST.sha256.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    return len(files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    target = parser.parse_args().output
    print(f"Packaged {package(target)} allowlisted files: {target}")
