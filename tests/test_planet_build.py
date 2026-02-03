from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from satpass.build import build_all
from satpass.config import load_config
from tests.conftest import _ensure_ephemeris_cached


def _setup_ephemeris(state_dir: Path) -> None:
    """Copy the cached ephemeris into a test state_dir."""
    cached = _ensure_ephemeris_cached()
    dest_dir = state_dir / "ephemeris"
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(cached, dest_dir / "de421.bsp")


def test_build_writes_planet_manifest(tmp_path: Path) -> None:
    config_data = {
        "version": 1,
        "repo_url": "https://github.com/test/repo",
        "site": {"title": "Test Site", "description": "Test description"},
        "defaults": {
            "horizon_days": 1,
            "tle_cache_hours": 12,
            "refresh_interval_hours": 6,
            "include_if_peak_elevation_deg": 30,
            "label_overhead_if_peak_elevation_deg": 80,
        },
        "featured_locations": [
            {"slug": "test", "name": "Test", "lat": 0.0, "lon": 0.0, "elevation_m": 0}
        ],
        "bundles": [
            {
                "slug": "planets-all",
                "name": "All Planets",
                "kind": "planetary",
                "planet_targets": [
                    "mercury",
                    "venus",
                    "mars",
                    "jupiter",
                    "saturn",
                    "uranus",
                    "neptune",
                ],
            }
        ],
        "featured_bundles": ["planets-all"],
        "allowed_requesters": ["testuser"],
        "request_defaults": {"slug_precision_decimals": 4, "max_satellites_per_request": 12},
        "request_db_path": str(tmp_path / "requests.sqlite"),
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config_data))
    config = load_config(config_path)

    output_dir = tmp_path / "site"
    state_dir = tmp_path / "state"
    requests_dir = tmp_path / "requests"
    requests_dir.mkdir()
    _setup_ephemeris(state_dir)

    build_all(config, output_dir, state_dir, requests_dir)

    manifest_path = output_dir / "feeds" / "index.json"
    assert manifest_path.exists()
    manifest = json.loads(manifest_path.read_text())

    planet_bundle = next(
        bundle for bundle in manifest["bundles"] if bundle["slug"] == "planets-all"
    )
    assert planet_bundle["kind"] == "planetary"
    assert planet_bundle["planet_targets"]

    feed_paths = {feed["path"] for feed in manifest["feeds"]}
    assert "feeds/test--planets-all.ics" in feed_paths
    assert (output_dir / "feeds" / "test--planets-all.ics").exists()
