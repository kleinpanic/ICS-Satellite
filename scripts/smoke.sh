#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON=".venv/bin/python"
SATPASS=".venv/bin/satpass"

if [ ! -x "$PYTHON" ]; then
  echo "Missing .venv/bin/python. Run make dev first." >&2
  exit 1
fi

if [ ! -x "$SATPASS" ]; then
  echo "Missing .venv/bin/satpass. Run make dev first." >&2
  exit 1
fi

tmp_requests="$(mktemp -d)"
tmp_manifest="$(mktemp)"
tmp_manifest_after="$(mktemp)"
tmp_ics="$(mktemp)"
tmp_expected_ics="$(mktemp)"
db_backup=""
db_existed="false"
smoke_port="${SMOKE_PORT:-8000}"

cleanup() {
  if [ -n "${server_pid:-}" ]; then
    kill "$server_pid" >/dev/null 2>&1 || true
  fi
  if [ -n "$db_backup" ] && [ -f "$db_backup" ]; then
    cp "$db_backup" data/requests.sqlite
    rm -f "$db_backup"
  elif [ "$db_existed" = "false" ] && [ -f data/requests.sqlite ]; then
    rm -f data/requests.sqlite
  fi
  rm -rf "$tmp_requests" "$tmp_manifest" "$tmp_manifest_after" "$tmp_ics" "$tmp_expected_ics"
}

trap cleanup EXIT

if [ -f data/requests.sqlite ]; then
  db_backup="$(mktemp)"
  cp data/requests.sqlite "$db_backup"
  db_existed="true"
fi

rm -rf site
make build

if ! $PYTHON - << PY
import socket
import sys

port = int("${smoke_port}")
sock = socket.socket()
try:
    sock.bind(("127.0.0.1", port))
except OSError:
    print(f"Port {port} is unavailable. Set SMOKE_PORT to a free port.", file=sys.stderr)
    sys.exit(1)
finally:
    sock.close()
PY
then
  exit 1
fi

$PYTHON -m http.server --directory site "$smoke_port" >/tmp/satpass-serve.log 2>&1 &
server_pid=$!
sleep 1

curl -fsS "http://127.0.0.1:${smoke_port}/feeds/index.json" -o "$tmp_manifest"
python3 -m json.tool "$tmp_manifest" >/dev/null

MANIFEST_PATH="$tmp_manifest"
feed_path="$(
  MANIFEST_PATH="$MANIFEST_PATH" $PYTHON - << 'PY'
import json
import os
from pathlib import Path

data = json.loads(Path(os.environ["MANIFEST_PATH"]).read_text())
print(data["feeds"][0]["path"])
PY
)"

curl -fsS "http://127.0.0.1:${smoke_port}/${feed_path}" -o "$tmp_ics"
head -n 20 "$tmp_ics"
grep -q '^BEGIN:VCALENDAR' "$tmp_ics"
grep -q '^PRODID:-//satpass//' "$tmp_ics"

cat > "${tmp_requests}/request.yaml" << 'EOF'
name: Smoke Test
lat: 40.7128
lon: -74.0060
bundle_slug: iss
selected_norad_ids: []
EOF

rm -rf site
$SATPASS build --config config/config.yaml --out site/ --requests "$tmp_requests" --catalog none

kill "$server_pid" >/dev/null 2>&1 || true
$PYTHON -m http.server --directory site "$smoke_port" >/tmp/satpass-serve.log 2>&1 &
server_pid=$!
sleep 1

curl -fsS "http://127.0.0.1:${smoke_port}/feeds/index.json" -o "$tmp_manifest_after"
python3 -m json.tool "$tmp_manifest_after" >/dev/null

MANIFEST_AFTER_PATH="$tmp_manifest_after" $PYTHON - << 'PY'
import json
import os
from collections import Counter
from pathlib import Path
from satpass.config import load_config
from satpass.slug import compute_location_slug, compute_request_feed_slug

manifest = json.loads(Path(os.environ["MANIFEST_AFTER_PATH"]).read_text())
paths = [feed["path"] for feed in manifest["feeds"]]
dups = [path for path, count in Counter(paths).items() if count > 1]
if dups:
    raise SystemExit(f"Duplicate feed paths found: {dups}")

config = load_config(Path("config/config.yaml"))
precision = config.request_defaults.slug_precision_decimals
location_slug = compute_location_slug(40.7128, -74.0060, precision)
feed_slug = compute_request_feed_slug(
    location_slug=location_slug,
    bundle_slug="iss",
    selected_norad_ids=[],
)
expected_path = f"feeds/{feed_slug}.ics"
if expected_path not in paths:
    raise SystemExit(f"Expected feed path not found: {expected_path}")
PY

expected_path="$(
  $PYTHON - << 'PY'
from satpass.config import load_config
from satpass.slug import compute_location_slug, compute_request_feed_slug
from pathlib import Path

config = load_config(Path("config/config.yaml"))
precision = config.request_defaults.slug_precision_decimals
location_slug = compute_location_slug(40.7128, -74.0060, precision)
feed_slug = compute_request_feed_slug(
    location_slug=location_slug,
    bundle_slug="iss",
    selected_norad_ids=[],
)
print(f"feeds/{feed_slug}.ics")
PY
)"

curl -fsS "http://127.0.0.1:${smoke_port}/${expected_path}" -o "$tmp_expected_ics"
head -n 20 "$tmp_expected_ics"
grep -q '^BEGIN:VCALENDAR' "$tmp_expected_ics"
grep -q '^PRODID:-//satpass//' "$tmp_expected_ics"
