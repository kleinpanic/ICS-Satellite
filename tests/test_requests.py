"""Tests for request handling functionality."""

from pathlib import Path

import pytest
import yaml

from satpass.config import (
    ConfigError,
    RequestDefaults,
    RequestedLocation,
    load_config,
    load_requests,
)
from satpass.slug import compute_location_slug


def _make_test_config(tmp_path: Path):
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
        "request_defaults": {"slug_precision_decimals": 4, "max_satellites_per_request": 12},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config_data))
    return load_config(path)


class TestRequestedLocation:
    """Tests for RequestedLocation validation."""

    def test_valid_requested_location(self) -> None:
        req = RequestedLocation(
            slug="lat47p6062_lonm122p3321",
            lat=47.6062,
            lon=-122.3321,
            bundle_slug="stations",
            selected_norad_ids=[25544],
        )
        assert req.slug == "lat47p6062_lonm122p3321"
        assert req.lat == 47.6062
        assert req.lon == -122.3321
        assert req.bundle_slug == "stations"
        assert req.selected_norad_ids == [25544]

    def test_lat_bounds_lower(self) -> None:
        with pytest.raises(ValueError, match="lat must be between"):
            RequestedLocation(
                slug="test",
                lat=-91.0,
                lon=0.0,
                bundle_slug="stations",
            )

    def test_lat_bounds_upper(self) -> None:
        with pytest.raises(ValueError, match="lat must be between"):
            RequestedLocation(
                slug="test",
                lat=91.0,
                lon=0.0,
                bundle_slug="stations",
            )

    def test_lon_bounds_lower(self) -> None:
        with pytest.raises(ValueError, match="lon must be between"):
            RequestedLocation(
                slug="test",
                lat=0.0,
                lon=-181.0,
                bundle_slug="stations",
            )

    def test_lon_bounds_upper(self) -> None:
        with pytest.raises(ValueError, match="lon must be between"):
            RequestedLocation(
                slug="test",
                lat=0.0,
                lon=181.0,
                bundle_slug="stations",
            )

    def test_optional_fields(self) -> None:
        req = RequestedLocation(
            slug="test",
            lat=0.0,
            lon=0.0,
            bundle_slug="stations",
        )
        assert req.name is None
        assert req.elevation_m == 0
        assert req.selected_norad_ids is None
        assert req.requested_by is None
        assert req.requested_at is None

    def test_selected_norad_ids_invalid(self) -> None:
        with pytest.raises(ValueError):
            RequestedLocation(
                slug="test",
                lat=0.0,
                lon=0.0,
                bundle_slug="stations",
                selected_norad_ids=[-1],
            )

    def test_to_location_with_name(self) -> None:
        req = RequestedLocation(
            slug="test",
            name="Test City",
            lat=47.6062,
            lon=-122.3321,
            bundle_slug="stations",
        )
        loc = req.to_location(precision=4)
        assert loc.slug == "test"
        assert loc.name == "Test City"
        assert loc.lat == 47.6062
        assert loc.lon == -122.3321

    def test_to_location_without_name(self) -> None:
        req = RequestedLocation(
            slug="test",
            lat=47.6062,
            lon=-122.3321,
            bundle_slug="stations",
        )
        loc = req.to_location(precision=4)
        assert loc.name == "Custom (47.6062, -122.3321)"

    def test_to_location_with_feed_slug(self) -> None:
        req = RequestedLocation(
            slug="lat47p6062_lonm122p3321--stations",
            lat=47.6062,
            lon=-122.3321,
            bundle_slug="stations",
        )
        loc = req.to_location(precision=4)
        assert loc.slug == "lat47p6062_lonm122p3321"

    def test_to_location_computes_slug_with_precision(self) -> None:
        req = RequestedLocation(
            lat=47.6062,
            lon=-122.3321,
            bundle_slug="stations",
        )
        loc = req.to_location(precision=6)
        assert loc.slug == compute_location_slug(47.6062, -122.3321, 6)


class TestRequestDefaults:
    """Tests for RequestDefaults."""

    def test_default_values(self) -> None:
        defaults = RequestDefaults()
        assert defaults.slug_precision_decimals == 4
        assert defaults.horizon_days is None
        assert defaults.max_satellites_per_request == 12

    def test_custom_precision(self) -> None:
        defaults = RequestDefaults(slug_precision_decimals=6)
        assert defaults.slug_precision_decimals == 6

    def test_precision_bounds(self) -> None:
        with pytest.raises(ValueError):
            RequestDefaults(slug_precision_decimals=0)
        with pytest.raises(ValueError):
            RequestDefaults(slug_precision_decimals=9)

    def test_max_satellites_bounds(self) -> None:
        with pytest.raises(ValueError):
            RequestDefaults(max_satellites_per_request=0)


class TestLoadRequests:
    """Tests for load_requests function."""

    def test_empty_requests_dir(self, tmp_path: Path) -> None:
        config = _make_test_config(tmp_path)
        requests_dir = tmp_path / "requests"
        requests_dir.mkdir()
        requests = load_requests(requests_dir, config)
        assert requests == []

    def test_nonexistent_requests_dir(self, tmp_path: Path) -> None:
        config = _make_test_config(tmp_path)
        requests_dir = tmp_path / "nonexistent"
        requests = load_requests(requests_dir, config)
        assert requests == []

    def test_valid_request_file(self, tmp_path: Path) -> None:
        config = _make_test_config(tmp_path)
        requests_dir = tmp_path / "requests"
        requests_dir.mkdir()

        request_data = {
            "slug": "lat40p7128_lonm74p0060--stations",
            "lat": 40.7128,
            "lon": -74.0060,
            "bundle_slug": "stations",
            "requested_by": "testuser",
        }
        (requests_dir / "test.yaml").write_text(yaml.dump(request_data))

        requests = load_requests(requests_dir, config)
        assert len(requests) == 1
        assert requests[0].slug == "lat40p7128_lonm74p0060--stations"
        assert requests[0].lat == 40.7128
        assert requests[0].lon == -74.0060
        assert requests[0].bundle_slug == "stations"

    def test_request_file_missing_slug(self, tmp_path: Path) -> None:
        config = _make_test_config(tmp_path)
        requests_dir = tmp_path / "requests"
        requests_dir.mkdir()

        request_data = {
            "lat": 40.7128,
            "lon": -74.0060,
            "bundle_slug": "stations",
        }
        (requests_dir / "missing-slug.yaml").write_text(yaml.safe_dump(request_data))

        requests = load_requests(requests_dir, config)
        assert len(requests) == 1
        assert requests[0].slug == "lat40p7128_lonm74p0060"

    def test_invalid_bundle_slug(self, tmp_path: Path) -> None:
        config = _make_test_config(tmp_path)
        requests_dir = tmp_path / "requests"
        requests_dir.mkdir()

        request_data = {
            "slug": "test",
            "lat": 40.7128,
            "lon": -74.0060,
            "bundle_slug": "nonexistent_bundle",
        }
        (requests_dir / "test.yaml").write_text(yaml.dump(request_data))

        with pytest.raises(ConfigError, match="unknown bundle"):
            load_requests(requests_dir, config)

    def test_invalid_lat_in_request(self, tmp_path: Path) -> None:
        config = _make_test_config(tmp_path)
        requests_dir = tmp_path / "requests"
        requests_dir.mkdir()

        request_data = {
            "slug": "test",
            "lat": 100.0,  # Invalid
            "lon": -74.0060,
            "bundle_slug": "stations",
        }
        (requests_dir / "test.yaml").write_text(yaml.dump(request_data))

        with pytest.raises(ConfigError):
            load_requests(requests_dir, config)


class TestAllowlist:
    """Tests for allowlist in config."""

    def test_config_has_allowed_requesters(self) -> None:
        config = load_config(Path("config/config.yaml"))
        assert hasattr(config, "allowed_requesters")
        assert isinstance(config.allowed_requesters, list)

    def test_config_has_request_defaults(self) -> None:
        config = load_config(Path("config/config.yaml"))
        assert hasattr(config, "request_defaults")
        assert config.request_defaults.slug_precision_decimals == 4
