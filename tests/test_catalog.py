from pathlib import Path
from unittest.mock import patch

import yaml

from satpass.catalog import build_bundle_catalog, read_catalog_metadata
from satpass.config import load_config


def _make_config(tmp_path: Path) -> Path:
    config_data = {
        "version": 1,
        "repo_url": "https://github.com/test/repo",
        "site": {"title": "Test", "description": "Test"},
        "defaults": {
            "horizon_days": 1,
            "tle_cache_hours": 12,
            "refresh_interval_hours": 6,
            "include_if_peak_elevation_deg": 30,
            "label_overhead_if_peak_elevation_deg": 80,
        },
        "featured_locations": [
            {"slug": "test", "name": "Test", "lat": 0, "lon": 0, "elevation_m": 0}
        ],
        "bundles": [{"slug": "stations", "name": "Stations", "celestrak_group": "stations"}],
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config_data))
    return path


@patch("satpass.catalog.fetch_tles")
def test_catalog_build_writes_metadata(mock_fetch_tles: patch, tmp_path: Path) -> None:
    from satpass.tle import TLE

    mock_fetch_tles.return_value = [
        TLE(
            name="ISS",
            line1="1 25544U 98067A   24120.51782528  .00021784  00000-0  38309-3 0  9991",
            line2="2 25544  51.6411 159.9641 0004568  37.1152  67.4875 15.50283102447526",
            norad_id=25544,
        ),
        TLE(
            name="TEST 2",
            line1="1 40909U 15049E   24120.51782528  .00021784  00000-0  38309-3 0  9991",
            line2="2 40909  51.6411 159.9641 0004568  37.1152  67.4875 15.50283102447526",
            norad_id=40909,
        ),
    ]

    config = load_config(_make_config(tmp_path))
    config.bundles[0].satellite_listing_limit = 1

    output_dir = tmp_path / "site"
    state_dir = tmp_path / "state"

    result = build_bundle_catalog(
        config=config,
        bundle=config.bundles[0],
        output_dir=output_dir,
        state_dir=state_dir,
    )

    assert result.path.exists()
    metadata = read_catalog_metadata(result.path)
    assert metadata is not None
    assert metadata["satellites_total"] == 2
    assert metadata["satellites_limit"] == 1
    assert metadata["satellites_truncated"] is True
