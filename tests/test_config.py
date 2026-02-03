from pathlib import Path

import pytest

from satpass.config import ConfigError, load_config, resolve_featured_locations


def test_config_loads() -> None:
    config = load_config(Path("config/config.yaml"))
    assert resolve_featured_locations(config)
    assert config.bundles


def test_duplicate_slugs_rejected(tmp_path: Path) -> None:
    data = """
version: 1
repo_url: "https://example.com/repo"
site:
  title: "Test"
  description: "Test"

defaults:
  horizon_days: 1
  tle_cache_hours: 1
  refresh_interval_hours: 1
  include_if_peak_elevation_deg: 10
  label_overhead_if_peak_elevation_deg: 20

featured_locations:
  - slug: "same"
    name: "A"
    lat: 0
    lon: 0
  - slug: "same"
    name: "B"
    lat: 1
    lon: 1

bundles:
  - slug: "bundle"
    name: "Bundle"
    celestrak_group: "stations"
"""
    path = tmp_path / "config.yaml"
    path.write_text(data)
    with pytest.raises(ConfigError):
        load_config(path)
