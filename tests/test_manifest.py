import json
from datetime import datetime, timezone
from pathlib import Path

from satpass import __version__
from satpass.config import Location, load_config, resolve_featured_locations
from satpass.site import FeedEntry, build_manifest


def test_manifest_contains_feeds() -> None:
    config = load_config(Path("config/config.yaml"))
    featured_locations = resolve_featured_locations(config)
    feed = FeedEntry(
        location=featured_locations[0],
        bundle=config.bundles[0],
        path="feeds/test.ics",
    )
    manifest = build_manifest(
        config=config,
        feeds=[feed],
        generated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    assert manifest["feeds"][0]["path"] == "feeds/test.ics"
    assert manifest["featured_locations"][0]["slug"] == featured_locations[0].slug
    assert manifest["request_defaults"]["max_satellites_per_request"] == 12
    assert "allowlist_enabled" in manifest["request_defaults"]
    assert manifest["build"]["version"] == __version__
    assert "stats" in manifest


def test_manifest_dedupes_feed_paths() -> None:
    config = load_config(Path("config/config.yaml"))
    featured_locations = resolve_featured_locations(config)
    location = featured_locations[0]
    bundle = config.bundles[0]
    featured_feed = FeedEntry(location=location, bundle=bundle, path="feeds/shared.ics")
    requested_feed = FeedEntry(
        location=location,
        bundle=bundle,
        path="feeds/shared.ics",
        selected_norad_ids=[25544],
    )

    manifest = build_manifest(
        config=config,
        feeds=[featured_feed],
        requested_feeds=[requested_feed],
        generated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    assert len(manifest["feeds"]) == 1
    assert manifest["feeds"][0]["path"] == "feeds/shared.ics"


def test_manifest_locations_include_requested() -> None:
    config = load_config(Path("config/config.yaml"))
    featured_location = resolve_featured_locations(config)[0]
    requested_location = Location(
        slug="lat0p1000_lon0p2000",
        name="Requested Location",
        lat=0.1,
        lon=0.2,
    )
    featured_feed = FeedEntry(
        location=featured_location,
        bundle=config.bundles[0],
        path="feeds/featured.ics",
    )
    requested_feed = FeedEntry(
        location=requested_location,
        bundle=config.bundles[0],
        path="feeds/requested.ics",
    )

    manifest = build_manifest(
        config=config,
        feeds=[featured_feed],
        requested_feeds=[requested_feed],
        generated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    locations = {loc["slug"]: loc for loc in manifest["locations"]}
    assert featured_location.slug in locations
    assert requested_location.slug in locations
    assert locations[featured_location.slug]["featured"] is True
    assert locations[requested_location.slug]["featured"] is False
    assert locations[requested_location.slug]["requested"] is True
    assert "location_key" in locations[requested_location.slug]


def test_manifest_catalog_path_absent_when_no_catalog(tmp_path: Path) -> None:
    """catalog_path should be None when catalog file does not exist."""
    config = load_config(Path("config/config.yaml"))
    featured_locations = resolve_featured_locations(config)
    sat_bundle = next(b for b in config.bundles if b.kind == "satellite")
    feed = FeedEntry(
        location=featured_locations[0],
        bundle=sat_bundle,
        path="feeds/test.ics",
    )
    catalog_dir = tmp_path / "catalog"
    catalog_dir.mkdir()
    # Do NOT create the catalog file

    manifest = build_manifest(
        config=config,
        feeds=[feed],
        generated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        catalog_dir=catalog_dir,
    )

    bundle_entry = next(b for b in manifest["bundles"] if b["slug"] == sat_bundle.slug)
    assert bundle_entry["catalog_available"] is False
    assert bundle_entry["catalog_path"] is None


def test_manifest_catalog_path_present_when_catalog_exists(tmp_path: Path) -> None:
    """catalog_path should be set when catalog file exists."""
    config = load_config(Path("config/config.yaml"))
    featured_locations = resolve_featured_locations(config)
    sat_bundle = next(b for b in config.bundles if b.kind == "satellite")
    feed = FeedEntry(
        location=featured_locations[0],
        bundle=sat_bundle,
        path="feeds/test.ics",
    )
    catalog_dir = tmp_path / "catalog"
    catalog_dir.mkdir()
    catalog_data = {
        "generated_at": "2025-01-01T00:00:00Z",
        "satellites_total": 10,
        "satellites_limit": 100,
        "satellites_truncated": False,
    }
    (catalog_dir / f"{sat_bundle.slug}.json").write_text(json.dumps(catalog_data))

    manifest = build_manifest(
        config=config,
        feeds=[feed],
        generated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        catalog_dir=catalog_dir,
    )

    bundle_entry = next(b for b in manifest["bundles"] if b["slug"] == sat_bundle.slug)
    assert bundle_entry["catalog_available"] is True
    assert bundle_entry["catalog_path"] == f"catalog/{sat_bundle.slug}.json"


def test_manifest_planetary_bundles_have_no_catalog() -> None:
    """Planetary bundles should never have catalog_path set."""
    config = load_config(Path("config/config.yaml"))
    featured_locations = resolve_featured_locations(config)
    planet_bundle = next((b for b in config.bundles if b.kind == "planetary"), None)
    if planet_bundle is None:
        return
    feed = FeedEntry(
        location=featured_locations[0],
        bundle=planet_bundle,
        path="feeds/test-planet.ics",
    )
    manifest = build_manifest(
        config=config,
        feeds=[feed],
        generated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )

    bundle_entry = next(b for b in manifest["bundles"] if b["slug"] == planet_bundle.slug)
    assert bundle_entry["catalog_available"] is False
    assert bundle_entry["catalog_path"] is None
