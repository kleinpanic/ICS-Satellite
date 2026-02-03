#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from satpass.config import RequestedLocation, load_config
from satpass.requests_db import get_request_by_key, init_db, upsert_request
from satpass.slug import compute_location_slug


def _env(name: str, required: bool = True) -> str:
    value = os.environ.get(name)
    if required and not value:
        raise ValueError(f"Missing required env var: {name}")
    return value or ""


def main() -> int:
    try:
        lat = float(_env("REQUEST_LAT"))
        lon = float(_env("REQUEST_LON"))
        bundle_slug = _env("REQUEST_BUNDLE")
        slug_override = os.environ.get("REQUEST_SLUG") or None
        name = os.environ.get("REQUEST_NAME") or None
        selected_ids = json.loads(_env("REQUEST_SELECTED_IDS"))
        requested_by = os.environ.get("REQUESTED_BY") or None
        requested_at = os.environ.get("REQUESTED_AT") or None
    except Exception as exc:
        sys.stderr.write(f"Failed to read request inputs: {exc}\n")
        return 1

    if not isinstance(selected_ids, list):
        sys.stderr.write("REQUEST_SELECTED_IDS must be a JSON list.\n")
        return 1

    config = load_config(Path("config/config.yaml"))
    bundle = next((b for b in config.bundles if b.slug == bundle_slug), None)
    if not bundle:
        sys.stderr.write(f"Unknown bundle slug: {bundle_slug}\n")
        return 1
    if slug_override:
        try:
            slug_override = RequestedLocation.validate_slug(slug_override)
        except ValueError as exc:
            sys.stderr.write(f"Invalid slug override: {exc}\n")
            return 1
    if bundle.kind == "planetary":
        if selected_ids:
            sys.stderr.write("Planetary bundles cannot include selected NORAD IDs.\n")
            return 1
        selected_ids = []
    precision = config.request_defaults.slug_precision_decimals
    location_slug = slug_override or compute_location_slug(lat, lon, precision)

    request = RequestedLocation(
        slug=location_slug,
        name=name,
        lat=lat,
        lon=lon,
        elevation_m=0,
        bundle_slug=bundle_slug,
        selected_norad_ids=selected_ids,
        requested_by=requested_by,
        requested_at=requested_at,
    )

    db_path = Path(os.environ.get("REQUEST_DB_PATH") or config.request_db_path)
    conn = init_db(db_path)
    try:
        record = upsert_request(conn, request, precision=precision)
        if not get_request_by_key(conn, record.request_key):
            raise RuntimeError("Persisted request not found in DB after upsert.")
    except Exception as exc:
        sys.stderr.write(f"Failed to persist request: {exc}\n")
        return 1
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
