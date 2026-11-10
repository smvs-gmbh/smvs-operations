"""Build a narrow public-service archive using an explicit source allowlist."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    "__init__.py",
    "__main__.py",
    "crypto.py",
    "gateway.py",
    "mail.py",
    "models.py",
    "schema.py",
    "service.py",
    "settings.py",
    "store.py",
    "templates/confirmation.js",
    "templates/confirmation.css",
    "templates/confirm.html",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--platform", choices=("docker", "apache"), default="docker")
    args = parser.parse_args()
    files = {"app/__init__.py": (ROOT / "app/__init__.py").read_bytes()}
    for module in MODULES:
        name = "app/registration/" + module
        files[name] = (ROOT / name).read_bytes()
    names = ["requirements.txt", "nginx.conf.example"]
    names += (
        ["Dockerfile", "README.md"]
        if args.platform == "docker"
        else [
            "README-apache.md",
            "apache-vhost.conf.example",
            "start-intake.sh",
            "supervisor.conf.example",
        ]
    )
    for name in names:
        files[name] = (ROOT / "deploy/registration-intake" / name).read_bytes()
    files["registration-intake.env.example"] = (
        ROOT / "config/registration-intake.env.example"
    ).read_bytes()
    manifest = {
        name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())
    }
    files["MANIFEST.sha256.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(name, data)
    print(f"Packaged {len(files)} allowlisted files: {args.output}")


if __name__ == "__main__":
    main()
