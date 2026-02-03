from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from satpass.config import load_config
from satpass.requests_db import get_request_by_key, init_db
from satpass.slug import compute_location_slug, compute_request_feed_slug


def test_issueops_persist_script(tmp_path: Path) -> None:
    db_path = tmp_path / "requests.sqlite"
    env = os.environ.copy()
    env.update(
        {
            "REQUEST_LAT": "40.7128",
            "REQUEST_LON": "-74.0060",
            "REQUEST_BUNDLE": "iss",
            "REQUEST_NAME": "IssueOps Test",
            "REQUEST_SELECTED_IDS": json.dumps([]),
            "REQUESTED_BY": "tester",
            "REQUESTED_AT": "2026-02-01T00:00:00Z",
            "REQUEST_DB_PATH": str(db_path),
        }
    )

    result = subprocess.run(
        [sys.executable, "scripts/issueops_persist_request.py"],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    config = load_config(Path("config/config.yaml"))
    precision = config.request_defaults.slug_precision_decimals
    location_slug = compute_location_slug(40.7128, -74.0060, precision)
    request_key = compute_request_feed_slug(
        location_slug=location_slug,
        bundle_slug="iss",
        selected_norad_ids=[],
    )

    conn = init_db(db_path)
    try:
        record = get_request_by_key(conn, request_key)
    finally:
        conn.close()
    assert record is not None


def test_issueops_persist_planetary_bundle(tmp_path: Path) -> None:
    """Planetary bundles (e.g. planets-all) must be accepted by the persist script."""
    db_path = tmp_path / "requests.sqlite"
    env = os.environ.copy()
    env.update(
        {
            "REQUEST_LAT": "37.2296",
            "REQUEST_LON": "-80.4139",
            "REQUEST_BUNDLE": "planets-all",
            "REQUEST_NAME": "Blacksburg VA",
            "REQUEST_SELECTED_IDS": json.dumps([]),
            "REQUESTED_BY": "tester",
            "REQUESTED_AT": "2026-02-01T00:00:00Z",
            "REQUEST_DB_PATH": str(db_path),
        }
    )

    result = subprocess.run(
        [sys.executable, "scripts/issueops_persist_request.py"],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    config = load_config(Path("config/config.yaml"))
    precision = config.request_defaults.slug_precision_decimals
    location_slug = compute_location_slug(37.2296, -80.4139, precision)
    request_key = compute_request_feed_slug(
        location_slug=location_slug,
        bundle_slug="planets-all",
        selected_norad_ids=[],
    )

    conn = init_db(db_path)
    try:
        record = get_request_by_key(conn, request_key)
    finally:
        conn.close()
    assert record is not None
    assert record.bundle_slug == "planets-all"
    assert record.selected_norad_ids == []


def test_issueops_persist_planetary_rejects_norad_ids(tmp_path: Path) -> None:
    """Planetary bundles must reject requests with selected_norad_ids."""
    db_path = tmp_path / "requests.sqlite"
    env = os.environ.copy()
    env.update(
        {
            "REQUEST_LAT": "37.2296",
            "REQUEST_LON": "-80.4139",
            "REQUEST_BUNDLE": "planets-all",
            "REQUEST_NAME": "Bad Request",
            "REQUEST_SELECTED_IDS": json.dumps([25544]),
            "REQUESTED_BY": "tester",
            "REQUESTED_AT": "2026-02-01T00:00:00Z",
            "REQUEST_DB_PATH": str(db_path),
        }
    )

    result = subprocess.run(
        [sys.executable, "scripts/issueops_persist_request.py"],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_config_bundles_include_planetary() -> None:
    """Config must include planetary bundles so the IssueOps validator accepts them."""
    config = load_config(Path("config/config.yaml"))
    bundle_slugs = {b.slug for b in config.bundles}
    planetary_slugs = {
        "planets-all",
        "planet-mercury",
        "planet-venus",
        "planet-mars",
        "planet-jupiter",
        "planet-saturn",
        "planet-uranus",
        "planet-neptune",
    }
    missing = planetary_slugs - bundle_slugs
    assert not missing, f"Config missing planetary bundles: {missing}"

    for slug in planetary_slugs:
        bundle = next(b for b in config.bundles if b.slug == slug)
        assert bundle.kind == "planetary", f"Bundle {slug} should be planetary"
