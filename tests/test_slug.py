"""Tests for the slug module."""

from satpass.slug import (
    compute_feed_slug,
    compute_location_slug,
    compute_request_feed_slug,
    format_coordinate,
    parse_feed_slug,
    parse_location_slug,
    selection_hash,
)


class TestFormatCoordinate:
    """Tests for format_coordinate function."""

    def test_positive_coordinate(self) -> None:
        assert format_coordinate(47.6062, 4) == "47p6062"

    def test_negative_coordinate(self) -> None:
        assert format_coordinate(-122.3321, 4) == "m122p3321"

    def test_zero_coordinate(self) -> None:
        assert format_coordinate(0.0, 4) == "0p0000"

    def test_negative_zero_rounds_to_positive(self) -> None:
        # -0.00001 rounds to 0.0000 with precision 4
        result = format_coordinate(-0.00001, 4)
        assert result == "0p0000"

    def test_rounding_up(self) -> None:
        assert format_coordinate(47.60625, 4) == "47p6063"

    def test_rounding_down(self) -> None:
        assert format_coordinate(47.60624, 4) == "47p6062"

    def test_precision_zero(self) -> None:
        # 47.6062 rounds to 48 with precision 0
        assert format_coordinate(47.6062, 0) == "48"
        assert format_coordinate(47.4999, 0) == "47"

    def test_precision_one(self) -> None:
        assert format_coordinate(47.6062, 1) == "47p6"

    def test_precision_eight(self) -> None:
        assert format_coordinate(47.60621234, 8) == "47p60621234"


class TestComputeLocationSlug:
    """Tests for compute_location_slug function."""

    def test_basic_slug(self) -> None:
        slug = compute_location_slug(47.6062, -122.3321, 4)
        assert slug == "lat47p6062_lonm122p3321"

    def test_slug_determinism(self) -> None:
        """Same inputs always produce the same slug."""
        slug1 = compute_location_slug(40.7128, -74.0060, 4)
        slug2 = compute_location_slug(40.7128, -74.0060, 4)
        assert slug1 == slug2

    def test_slug_uniqueness(self) -> None:
        """Different inputs produce different slugs."""
        slug1 = compute_location_slug(40.7128, -74.0060, 4)
        slug2 = compute_location_slug(40.7129, -74.0060, 4)
        assert slug1 != slug2

    def test_precision_affects_slug(self) -> None:
        """Different precision values produce different slugs."""
        slug1 = compute_location_slug(47.60621, -122.33211, 4)
        slug2 = compute_location_slug(47.60621, -122.33211, 5)
        assert slug1 != slug2

    def test_equator_prime_meridian(self) -> None:
        slug = compute_location_slug(0.0, 0.0, 4)
        assert slug == "lat0p0000_lon0p0000"

    def test_extreme_coordinates(self) -> None:
        """Test coordinates at extreme values."""
        slug_north = compute_location_slug(90.0, 0.0, 4)
        slug_south = compute_location_slug(-90.0, 0.0, 4)
        slug_east = compute_location_slug(0.0, 180.0, 4)
        slug_west = compute_location_slug(0.0, -180.0, 4)

        assert "lat90p0000" in slug_north
        assert "latm90p0000" in slug_south
        assert "lon180p0000" in slug_east
        assert "lonm180p0000" in slug_west


class TestComputeFeedSlug:
    """Tests for compute_feed_slug function."""

    def test_basic_feed_slug(self) -> None:
        slug = compute_feed_slug(47.6062, -122.3321, "stations", 4)
        assert slug == "lat47p6062_lonm122p3321--stations"

    def test_different_bundles(self) -> None:
        """Different bundles produce different slugs."""
        slug1 = compute_feed_slug(47.6062, -122.3321, "stations", 4)
        slug2 = compute_feed_slug(47.6062, -122.3321, "noaa", 4)
        assert slug1 != slug2
        assert slug1.endswith("--stations")
        assert slug2.endswith("--noaa")


class TestRequestFeedSlug:
    """Tests for compute_request_feed_slug."""

    def test_request_feed_slug_no_selection(self) -> None:
        slug = compute_request_feed_slug(
            location_slug="lat47p6062_lonm122p3321",
            bundle_slug="stations",
            selected_norad_ids=None,
        )
        assert slug == "lat47p6062_lonm122p3321--stations"

    def test_request_feed_slug_with_selection(self) -> None:
        slug = compute_request_feed_slug(
            location_slug="lat47p6062_lonm122p3321",
            bundle_slug="stations",
            selected_norad_ids=[25544, 33591],
        )
        assert slug.startswith("lat47p6062_lonm122p3321--stations--sel-")

    def test_selection_hash_deterministic(self) -> None:
        digest1 = selection_hash([33591, 25544])
        digest2 = selection_hash([25544, 33591, 25544])
        assert digest1 == digest2


class TestParseLocationSlug:
    """Tests for parse_location_slug function."""

    def test_parse_valid_slug(self) -> None:
        result = parse_location_slug("lat47p6062_lonm122p3321")
        assert result is not None
        lat, lon = result
        assert abs(lat - 47.6062) < 0.0001
        assert abs(lon - (-122.3321)) < 0.0001

    def test_parse_roundtrip(self) -> None:
        """Parsing a generated slug recovers the original values."""
        lat, lon = 40.7128, -74.0060
        slug = compute_location_slug(lat, lon, 4)
        result = parse_location_slug(slug)
        assert result is not None
        parsed_lat, parsed_lon = result
        assert abs(parsed_lat - round(lat, 4)) < 0.00001
        assert abs(parsed_lon - round(lon, 4)) < 0.00001

    def test_parse_invalid_slug_no_lat_prefix(self) -> None:
        assert parse_location_slug("47p6062_lonm122p3321") is None

    def test_parse_invalid_slug_no_lon(self) -> None:
        assert parse_location_slug("lat47p6062") is None


class TestParseFeedSlug:
    """Tests for parse_feed_slug function."""

    def test_parse_valid_feed_slug(self) -> None:
        result = parse_feed_slug("lat47p6062_lonm122p3321--stations")
        assert result is not None
        lat, lon, bundle = result
        assert abs(lat - 47.6062) < 0.0001
        assert abs(lon - (-122.3321)) < 0.0001
        assert bundle == "stations"

    def test_parse_feed_slug_roundtrip(self) -> None:
        """Parsing a generated feed slug recovers the original values."""
        lat, lon, bundle = 40.7128, -74.0060, "noaa"
        slug = compute_feed_slug(lat, lon, bundle, 4)
        result = parse_feed_slug(slug)
        assert result is not None
        parsed_lat, parsed_lon, parsed_bundle = result
        assert abs(parsed_lat - round(lat, 4)) < 0.00001
        assert abs(parsed_lon - round(lon, 4)) < 0.00001
        assert parsed_bundle == bundle

    def test_parse_invalid_no_separator(self) -> None:
        assert parse_feed_slug("lat47p6062_lonm122p3321") is None
