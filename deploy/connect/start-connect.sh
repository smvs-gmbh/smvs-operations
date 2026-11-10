#!/bin/sh
set -eu
umask 077
cd -- "$(dirname -- "$0")"
exec .venv/bin/uvicorn app.connect.gateway:from_environment --factory --host 127.0.0.1 --port 8013 --no-access-log --no-proxy-headers
