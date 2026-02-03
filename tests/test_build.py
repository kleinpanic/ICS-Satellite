"""Tests for the build module."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from satpass import __version__
from satpass.build import build_all
from satpass.config import Config, load_config
from satpass.requests_db import init_db, load_requests_from_db, upsert_request
from satpass.seed import seed_requests
from satpass.slug import compute_location_slug, compute_request_feed_slug


@pytest.fixture
def minimal_config(tmp_path: Path) -> Config:
    """Create a minimal config for testing."""
    config_data = {
        "version": 1,
        "repo_url": "https://github.com/test/repo",
        "site": {
            "title": "Test Site",
            "description": "Test description",
        },
        "defaults": {
            "horizon_days": 1,
            "tle_cache_hours": 12,
            "refresh_interval_hours": 6,
            "include_if_peak_elevation_deg": 30,
            "label_overhead_if_peak_elevation_deg": 80,
        },
        "featured_locations": [
            {"slug": "test", "name": "Test", "lat": 47.6062, "lon": -122.3321, "elevation_m": 0}
        ],
        "bundles": [{"slug": "stations", "name": "Stations", "celestrak_group": "stations"}],
        "allowed_requesters": ["testuser"],
        "request_defaults": {"slug_precision_decimals": 4, "max_satellites_per_request": 12},
        "request_db_path": str(tmp_path / "requests.sqlite"),
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config_data))
    return load_config(config_path)


class TestBuildWithRequests:
    """Tests for build including request files."""

    @patch("satpass.build.fetch_tles")
    def test_build_includes_requests(
        self, mock_fetch_tles: patch, tmp_path: Path, minimal_config: Config
    ) -> None:
        """Build should include feeds for request files."""
        from satpass.tle import TLE

        # Mock TLE fetch
        mock_tle = TLE(
            name="ISS",
            line1="1 25544U 98067A   24120.51782528  .00021784  00000-0  38309-3 0  9991",
            line2="2 25544  51.6411 159.9641 0004568  37.1152  67.4875 15.50283102447526",
            norad_id=25544,
        )
        mock_fetch_tles.return_value = [mock_tle]

        output_dir = tmp_path / "site"
        state_dir = tmp_path / "state"
        requests_dir = tmp_path / "requests"
        requests_dir.mkdir()

        # Create a request file - slug is just the location part
        request_data = {
            "slug": "lat40p7128_lonm74p006",
            "name": "NYC",
            "lat": 40.7128,
            "lon": -74.006,
            "elevation_m": 0,
            "bundle_slug": "stations",
            "requested_by": "testuser",
        }
        (requests_dir / "nyc.yaml").write_text(yaml.dump(request_data))

        feeds = build_all(minimal_config, output_dir, state_dir, requests_dir)

        # Should have both the configured location and the requested location
        assert len(feeds) == 2

        # Check the manifest includes the requested feed
        manifest_path = output_dir / "feeds" / "index.json"
        assert manifest_path.exists()
        manifest = json.loads(manifest_path.read_text())

        feed_paths = [f["path"] for f in manifest["feeds"]]
        assert "feeds/test--stations.ics" in feed_paths
        # Filename is location_slug--bundle_slug.ics
        assert "feeds/lat40p7128_lonm74p006--stations.ics" in feed_paths

        # Check requested flag
        requested_feeds = [f for f in manifest["feeds"] if f.get("requested")]
        assert len(requested_feeds) == 1
        assert requested_feeds[0]["location_slug"] == "lat40p7128_lonm74p006"

    @patch("satpass.build.fetch_tles")
    def test_manifest_contains_request_defaults(
        self, mock_fetch_tles: patch, tmp_path: Path, minimal_config: Config
    ) -> None:
        """Manifest should include request_defaults for the site JS."""
        from satpass.tle import TLE

        mock_tle = TLE(
            name="ISS",
            line1="1 25544U 98067A   24120.51782528  .00021784  00000-0  38309-3 0  9991",
            line2="2 25544  51.6411 159.9641 0004568  37.1152  67.4875 15.50283102447526",
            norad_id=25544,
        )
        mock_fetch_tles.return_value = [mock_tle]

        output_dir = tmp_path / "site"
        state_dir = tmp_path / "state"

        requests_dir = tmp_path / "requests"
        requests_dir.mkdir()
        build_all(minimal_config, output_dir, state_dir, requests_dir)

        manifest_path = output_dir / "feeds" / "index.json"
        manifest = json.loads(manifest_path.read_text())

        assert "request_defaults" in manifest
        assert manifest["request_defaults"]["slug_precision_decimals"] == 4
        bundle_entry = manifest["bundles"][0]
        assert bundle_entry["catalog_path"] is None
        assert bundle_entry["catalog_available"] is False

    @patch("satpass.build.fetch_tles")
    def test_requested_bundle_included_in_build(
        self, mock_fetch_tles: patch, tmp_path: Path
    ) -> None:
        """Requests for non-featured bundles must still be fetched and built."""
        from satpass.config import RequestedLocation
        from satpass.tle import TLE

        def _mock_fetch_tles(*, cache_dir, ttl_hours, groups, norad_ids):
            norad_id = 25544
            return [
                TLE(
                    name="TEST",
                    line1="1 25544U 98067A   24120.51782528  .00021784  00000-0  38309-3 0  9991",
                    line2="2 25544  51.6411 159.9641 0004568  37.1152  67.4875 15.50283102447526",
                    norad_id=norad_id,
                )
            ]

        mock_fetch_tles.side_effect = _mock_fetch_tles

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
                {"slug": "test", "name": "Test", "lat": 47.6062, "lon": -122.3321, "elevation_m": 0}
            ],
            "bundles": [
                {
                    "slug": "popular",
                    "name": "Popular",
                    "celestrak_group": "stations",
                    "norad_ids": [25544],
                },
                {
                    "slug": "iss",
                    "name": "ISS",
                    "celestrak_group": "stations",
                    "norad_ids": [25544],
                },
            ],
            "featured_bundles": ["popular"],
            "request_defaults": {"slug_precision_decimals": 4, "max_satellites_per_request": 12},
            "request_db_path": str(tmp_path / "requests.sqlite"),
        }
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump(config_data))
        config = load_config(config_path)

        conn = init_db(Path(config.request_db_path))
        try:
            req = RequestedLocation(
                lat=40.7128,
                lon=-74.0060,
                bundle_slug="iss",
            )
            upsert_request(conn, req, precision=config.request_defaults.slug_precision_decimals)
        finally:
            conn.close()

        output_dir = tmp_path / "site"
        state_dir = tmp_path / "state"
        requests_dir = tmp_path / "requests"
        requests_dir.mkdir()

        feeds = build_all(config, output_dir, state_dir, requests_dir)

        assert len(mock_fetch_tles.call_args_list) == 2

        location_slug = compute_location_slug(40.7128, -74.0060, 4)
        request_slug = compute_request_feed_slug(
            location_slug=location_slug,
            bundle_slug="iss",
            selected_norad_ids=[],
        )
        feed_paths = [feed.path for feed in feeds]
        assert f"feeds/{request_slug}.ics" in feed_paths

    @patch("satpass.build.fetch_tles")
    def test_request_selected_ids_validation(
        self, mock_fetch_tles: patch, tmp_path: Path, minimal_config: Config
    ) -> None:
        """Invalid requested satellites are dropped during canonicalization."""
        from satpass.tle import TLE

        mock_tle = TLE(
            name="ISS",
            line1="1 25544U 98067A   24120.51782528  .00021784  00000-0  38309-3 0  9991",
            line2="2 25544  51.6411 159.9641 0004568  37.1152  67.4875 15.50283102447526",
            norad_id=25544,
        )
        mock_fetch_tles.return_value = [mock_tle]

        output_dir = tmp_path / "site"
        state_dir = tmp_path / "state"
        requests_dir = tmp_path / "requests"
        requests_dir.mkdir()

        request_data = {
            "slug": "lat40p7128_lonm74p006",
            "name": "NYC",
            "lat": 40.7128,
            "lon": -74.006,
            "elevation_m": 0,
            "bundle_slug": "stations",
            "selected_norad_ids": [99999],
        }
        (requests_dir / "nyc.yaml").write_text(yaml.dump(request_data))

        build_all(minimal_config, output_dir, state_dir, requests_dir)
        conn = init_db(Path(minimal_config.request_db_path))
        try:
            requests = load_requests_from_db(conn)
        finally:
            conn.close()
        assert requests[0].selected_norad_ids == []

    @patch("satpass.build.fetch_tles")
    def test_full_selection_is_canonicalized(
        self, mock_fetch_tles: patch, tmp_path: Path, minimal_config: Config
    ) -> None:
        """Selecting all satellites should not produce selection hash slugs."""
        from satpass.tle import TLE

        mock_tle = TLE(
            name="ISS",
            line1="1 25544U 98067A   24120.51782528  .00021784  00000-0  38309-3 0  9991",
            line2="2 25544  51.6411 159.9641 0004568  37.1152  67.4875 15.50283102447526",
            norad_id=25544,
        )
        mock_fetch_tles.return_value = [mock_tle]

        output_dir = tmp_path / "site"
        state_dir = tmp_path / "state"
        requests_dir = tmp_path / "requests"
        requests_dir.mkdir()

        request_data = {
            "lat": 40.7128,
            "lon": -74.006,
            "bundle_slug": "stations",
            "selected_norad_ids": [25544],
        }
        (requests_dir / "nyc.yaml").write_text(yaml.dump(request_data))

        build_all(minimal_config, output_dir, state_dir, requests_dir)

        manifest_path = output_dir / "feeds" / "index.json"
        manifest = json.loads(manifest_path.read_text())
        feed_paths = [f["path"] for f in manifest["feeds"]]
        assert "feeds/lat40p7128_lonm74p0060--stations.ics" in feed_paths
        assert not any("--sel-" in path for path in feed_paths)

    @patch("satpass.build.fetch_tles")
    def test_manifest_feed_paths_sorted_and_unique(
        self, mock_fetch_tles: patch, tmp_path: Path, minimal_config: Config
    ) -> None:
        """Manifest feeds should be unique and sorted by path."""
        from satpass.tle import TLE

        mock_fetch_tles.return_value = [
            TLE(
                name="ISS",
                line1="1 25544U 98067A   24120.51782528  .00021784  00000-0  38309-3 0  9991",
                line2="2 25544  51.6411 159.9641 0004568  37.1152  67.4875 15.50283102447526",
                norad_id=25544,
            )
        ]

        output_dir = tmp_path / "site"
        state_dir = tmp_path / "state"
        requests_dir = tmp_path / "requests"
        requests_dir.mkdir()

        request_data = {
            "slug": "lat40p7128_lonm74p006",
            "name": "NYC",
            "lat": 40.7128,
            "lon": -74.006,
            "elevation_m": 0,
            "bundle_slug": "stations",
        }
        (requests_dir / "nyc.yaml").write_text(yaml.dump(request_data))

        build_all(minimal_config, output_dir, state_dir, requests_dir)

        manifest = json.loads((output_dir / "feeds" / "index.json").read_text())
        paths = [feed["path"] for feed in manifest["feeds"]]
        assert len(paths) == len(set(paths))
        assert paths == sorted(paths)


@patch("satpass.build.fetch_tles")
def test_build_includes_seeded_requests_for_non_featured_location(
    mock_fetch_tles: patch, tmp_path: Path
) -> None:
    from satpass.tle import TLE

    mock_fetch_tles.return_value = [
        TLE(
            name="ISS",
            line1="1 25544U 98067A   24120.51782528  .00021784  00000-0  38309-3 0  9991",
            line2="2 25544  51.6411 159.9641 0004568  37.1152  67.4875 15.50283102447526",
            norad_id=25544,
        )
    ]

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
            {"slug": "new-york", "name": "New York, NY", "lat": 40.7128, "lon": -74.006}
        ],
        "featured_bundles": ["popular"],
        "bundles": [
            {"slug": "popular", "name": "Popular", "norad_ids": [25544]},
            {"slug": "iss", "name": "ISS", "norad_ids": [25544]},
        ],
        "request_defaults": {"slug_precision_decimals": 4, "max_satellites_per_request": 12},
        "request_db_path": str(tmp_path / "requests.sqlite"),
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config_data))
    config = load_config(config_path)

    seed_data = {
        "requests": [
            {"lat": 37.2296, "lon": -80.4139, "bundle_slug": "iss"},
            {"lat": 37.2296, "lon": -80.4139, "bundle_slug": "popular"},
        ]
    }
    seed_path = tmp_path / "seed.yaml"
    seed_path.write_text(yaml.safe_dump(seed_data))
    seed_requests(
        config=config,
        seed_path=seed_path,
        db_path=Path(config.request_db_path),
        reset=True,
    )

    output_dir = tmp_path / "site"
    state_dir = tmp_path / "state"
    requests_dir = tmp_path / "requests"
    requests_dir.mkdir()

    build_all(config, output_dir, state_dir, requests_dir)

    manifest_path = output_dir / "feeds" / "index.json"
    manifest = json.loads(manifest_path.read_text())
    feed_paths = {f["path"] for f in manifest["feeds"]}

    assert "feeds/lat37p2296_lonm80p4139--iss.ics" in feed_paths
    assert "feeds/lat37p2296_lonm80p4139--popular.ics" in feed_paths


@patch("satpass.build.fetch_tles")
def test_manifest_includes_expanded_seeded_requests(mock_fetch_tles: patch, tmp_path: Path) -> None:
    """Build manifest should include expanded seeded request feeds."""
    from satpass.tle import TLE

    mock_tle = TLE(
        name="ISS",
        line1="1 25544U 98067A   24120.51782528  .00021784  00000-0  38309-3 0  9991",
        line2="2 25544  51.6411 159.9641 0004568  37.1152  67.4875 15.50283102447526",
        norad_id=25544,
    )
    mock_fetch_tles.return_value = [mock_tle]

    config = load_config(Path("config/config.yaml")).model_copy(
        update={
            "request_db_path": str(tmp_path / "requests.sqlite"),
            "featured_bundles": ["popular", "noaa-apt", "iss", "stations"],
        }
    )

    seed_requests(
        config=config,
        seed_path=Path("config/seeds/seed_requests.yaml"),
        db_path=Path(config.request_db_path),
        reset=True,
    )

    output_dir = tmp_path / "site"
    state_dir = tmp_path / "state"
    requests_dir = tmp_path / "requests"
    requests_dir.mkdir()

    build_all(config, output_dir, state_dir, requests_dir)

    manifest = json.loads((output_dir / "feeds" / "index.json").read_text())
    feed_paths = {feed["path"] for feed in manifest["feeds"]}
    precision = config.request_defaults.slug_precision_decimals

    expected = [
        (49.2827, -123.1207, "weather"),
        (40.4168, -3.7038, "galileo"),
        (-1.2921, 36.8219, "gnss"),
        (38.7223, -9.1393, "gps-ops"),
        (60.1699, 24.9384, "noaa-apt"),
    ]
    for lat, lon, bundle_slug in expected:
        location_slug = compute_location_slug(lat, lon, precision)
        feed_slug = compute_request_feed_slug(
            location_slug=location_slug,
            bundle_slug=bundle_slug,
            selected_norad_ids=[],
        )
        assert f"feeds/{feed_slug}.ics" in feed_paths


class TestICSOutput:
    """Tests for ICS output invariants."""

    @patch("satpass.build.fetch_tles")
    def test_ics_has_required_headers(
        self, mock_fetch_tles: patch, tmp_path: Path, minimal_config: Config
    ) -> None:
        """ICS files should have required headers."""
        from satpass.tle import TLE

        mock_tle = TLE(
            name="ISS",
            line1="1 25544U 98067A   24120.51782528  .00021784  00000-0  38309-3 0  9991",
            line2="2 25544  51.6411 159.9641 0004568  37.1152  67.4875 15.50283102447526",
            norad_id=25544,
        )
        mock_fetch_tles.return_value = [mock_tle]

        output_dir = tmp_path / "site"
        state_dir = tmp_path / "state"

        requests_dir = tmp_path / "requests"
        requests_dir.mkdir()
        build_all(minimal_config, output_dir, state_dir, requests_dir)

        ics_path = output_dir / "feeds" / "test--stations.ics"
        assert ics_path.exists()

        content = ics_path.read_text()
        assert "BEGIN:VCALENDAR" in content
        assert f"PRODID:-//satpass//{__version__}//EN" in content
        assert "VERSION:2.0" in content
        assert "X-WR-CALNAME:" in content
        assert "END:VCALENDAR" in content

    @patch("satpass.build.fetch_tles")
    def test_ics_uid_format_stable(
        self, mock_fetch_tles: patch, tmp_path: Path, minimal_config: Config
    ) -> None:
        """UID format should be stable and deterministic."""
        from satpass.tle import TLE

        mock_tle = TLE(
            name="ISS",
            line1="1 25544U 98067A   24120.51782528  .00021784  00000-0  38309-3 0  9991",
            line2="2 25544  51.6411 159.9641 0004568  37.1152  67.4875 15.50283102447526",
            norad_id=25544,
        )
        mock_fetch_tles.return_value = [mock_tle]

        output_dir = tmp_path / "site"
        state_dir = tmp_path / "state"

        requests_dir = tmp_path / "requests"
        requests_dir.mkdir()
        build_all(minimal_config, output_dir, state_dir, requests_dir)

        ics_path = output_dir / "feeds" / "test--stations.ics"
        content = ics_path.read_text()

        # Find all UIDs and verify format
        import re

        uids = re.findall(r"UID:(.*)", content)
        for uid in uids:
            # UID format: <location>-<bundle>-<norad_id>-<timestamp>
            parts = uid.split("-")
            assert len(parts) >= 4, f"UID format invalid: {uid}"
            # Should contain the location and bundle slugs
            assert "test" in uid
            assert "stations" in uid


@patch("satpass.build.fetch_tles")
def test_build_copies_favicon_assets(
    mock_fetch_tles: patch, tmp_path: Path, minimal_config: Config
) -> None:
    """Build should copy favicon assets into the output directory."""
    from satpass.tle import TLE

    mock_fetch_tles.return_value = [
        TLE(
            name="ISS",
            line1="1 25544U 98067A   24120.51782528  .00021784  00000-0  38309-3 0  9991",
            line2="2 25544  51.6411 159.9641 0004568  37.1152  67.4875 15.50283102447526",
            norad_id=25544,
        )
    ]

    output_dir = tmp_path / "site"
    state_dir = tmp_path / "state"
    requests_dir = tmp_path / "requests"
    requests_dir.mkdir()

    build_all(minimal_config, output_dir, state_dir, requests_dir)

    for filename in ("favicon.ico", "favicon.svg", "apple-touch-icon.png"):
        path = output_dir / filename
        assert path.exists(), f"Missing asset: {filename}"
        assert path.stat().st_size > 0, f"Empty asset: {filename}"
