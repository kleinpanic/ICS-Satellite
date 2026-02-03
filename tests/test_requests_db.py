"""Tests for request database handling."""

from pathlib import Path

import yaml

from satpass.config import RequestedLocation, load_config
from satpass.requests_db import (
    canonicalize_requests,
    dedupe_requests_by_signature,
    get_request_by_key,
    get_request_by_signature,
    init_db,
    list_requests,
    load_requests_from_db,
    location_key_for,
    migrate_yaml_requests,
    request_key_for,
    upsert_request,
    write_request_yaml,
)
from satpass.slug import compute_location_slug, compute_request_feed_slug


def test_upsert_dedupes_requests(tmp_path: Path) -> None:
    db_path = tmp_path / "requests.sqlite"
    conn = init_db(db_path)

    req = RequestedLocation(
        slug="lat47p6062_lonm122p3321",
        name="Seattle",
        lat=47.6062,
        lon=-122.3321,
        bundle_slug="stations",
        selected_norad_ids=[25544, 25544],
        requested_by="tester",
    )

    record1 = upsert_request(conn, req, precision=4)
    record2 = upsert_request(conn, req, precision=4)

    records = list_requests(conn)
    assert len(records) == 1
    assert record1.request_key == record2.request_key


def test_upsert_dedupes_by_location_key(tmp_path: Path) -> None:
    db_path = tmp_path / "requests.sqlite"
    conn = init_db(db_path)

    req_one = RequestedLocation(
        slug="custom-slug",
        name="Custom",
        lat=37.2296,
        lon=-80.4139,
        bundle_slug="stations",
        selected_norad_ids=[25544],
    )
    req_two = RequestedLocation(
        slug="lat37p2296_lonm80p4139",
        name="Custom",
        lat=37.2296,
        lon=-80.4139,
        bundle_slug="stations",
        selected_norad_ids=[25544],
    )

    record1 = upsert_request(conn, req_one, precision=4)
    record2 = upsert_request(conn, req_two, precision=4)

    assert record1.request_key == record2.request_key
    records = list_requests(conn)
    assert len(records) == 1
    signature = get_request_by_signature(
        conn,
        location_key=location_key_for(37.2296, -80.4139, 4),
        bundle_slug="stations",
        selected_norad_ids=[25544],
    )
    assert signature is not None


def test_dedupe_requests_by_signature(tmp_path: Path) -> None:
    db_path = tmp_path / "requests.sqlite"
    conn = init_db(db_path)

    req_one = RequestedLocation(
        slug="custom-slug",
        name="Custom",
        lat=37.2296,
        lon=-80.4139,
        bundle_slug="stations",
    )
    req_two = RequestedLocation(
        slug="lat37p2296_lonm80p4139",
        name="Custom",
        lat=37.2296,
        lon=-80.4139,
        bundle_slug="stations",
    )
    upsert_request(conn, req_one, precision=4)
    upsert_request(conn, req_two, precision=4)

    removed = dedupe_requests_by_signature(conn, 4)
    assert removed >= 0
    records = list_requests(conn)
    assert len(records) == 1


def test_upsert_keeps_distinct_requests(tmp_path: Path) -> None:
    db_path = tmp_path / "requests.sqlite"
    conn = init_db(db_path)

    req1 = RequestedLocation(
        slug="lat40p7128_lonm74p0060",
        name="NYC",
        lat=40.7128,
        lon=-74.0060,
        bundle_slug="stations",
        selected_norad_ids=[25544],
    )
    req2 = RequestedLocation(
        slug="lat47p6062_lonm122p3321",
        name="Seattle",
        lat=47.6062,
        lon=-122.3321,
        bundle_slug="iss",
        selected_norad_ids=[25544],
    )

    record1 = upsert_request(conn, req1, precision=4)
    record2 = upsert_request(conn, req2, precision=4)

    records = list_requests(conn)
    assert len(records) == 2
    assert {record1.request_key, record2.request_key} == {r.request_key for r in records}


def test_request_key_with_selection() -> None:
    key = request_key_for(
        location_slug="lat47p6062_lonm122p3321",
        bundle_slug="stations",
        selected_norad_ids=[25544, 33591],
    )
    assert key.startswith("lat47p6062_lonm122p3321--stations--sel-")


def test_write_request_yaml(tmp_path: Path) -> None:
    db_path = tmp_path / "requests.sqlite"
    conn = init_db(db_path)

    req = RequestedLocation(
        slug="lat40p7128_lonm74p0060",
        name="NYC",
        lat=40.7128,
        lon=-74.0060,
        bundle_slug="stations",
    )

    record = upsert_request(conn, req, precision=4)
    path = write_request_yaml(tmp_path, record)
    assert path.exists()
    loaded = path.read_text()
    assert "bundle_slug" in loaded


def test_get_request_by_key(tmp_path: Path) -> None:
    db_path = tmp_path / "requests.sqlite"
    conn = init_db(db_path)

    req = RequestedLocation(
        slug="lat40p7128_lonm74p0060",
        name="NYC",
        lat=40.7128,
        lon=-74.0060,
        bundle_slug="stations",
    )

    record = upsert_request(conn, req, precision=4)
    fetched = get_request_by_key(conn, record.request_key)
    assert fetched is not None
    assert fetched.request_key == record.request_key


def test_migrate_yaml_requests_dedupes(tmp_path: Path) -> None:
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
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config_data))
    config = load_config(config_path)

    requests_dir = tmp_path / "requests"
    requests_dir.mkdir()
    request_data = {
        "slug": "lat40p7128_lonm74p0060",
        "lat": 40.7128,
        "lon": -74.0060,
        "bundle_slug": "stations",
    }
    (requests_dir / "first.yaml").write_text(yaml.safe_dump(request_data))
    (requests_dir / "second.yaml").write_text(yaml.safe_dump(request_data))

    db_path = tmp_path / "requests.sqlite"
    conn = init_db(db_path)
    migrate_yaml_requests(config=config, conn=conn, requests_dir=requests_dir)
    records = list_requests(conn)
    assert len(records) == 1

    loaded = load_requests_from_db(conn)
    assert len(loaded) == 1
    assert loaded[0].bundle_slug == "stations"


def test_canonicalize_requests_collapses_full_selection(tmp_path: Path) -> None:
    db_path = tmp_path / "requests.sqlite"
    conn = init_db(db_path)

    req = RequestedLocation(
        slug="lat47p6062_lonm122p3321",
        name="Seattle",
        lat=47.6062,
        lon=-122.3321,
        bundle_slug="iss",
        selected_norad_ids=[25544],
    )
    record = upsert_request(conn, req, precision=4)

    updated = canonicalize_requests(conn, {"iss": [25544]}, 12)
    assert updated == 1

    records = list_requests(conn)
    assert len(records) == 1
    assert records[0].selected_norad_ids == []
    assert records[0].request_key == request_key_for(
        location_slug=record.location_slug,
        bundle_slug=record.bundle_slug,
        selected_norad_ids=[],
    )


def test_canonicalize_requests_applies_default_selection(tmp_path: Path) -> None:
    db_path = tmp_path / "requests.sqlite"
    conn = init_db(db_path)

    req = RequestedLocation(
        slug="lat40p7128_lonm74p0060",
        name="NYC",
        lat=40.7128,
        lon=-74.0060,
        bundle_slug="weather",
        selected_norad_ids=[],
    )
    upsert_request(conn, req, precision=4)

    updated = canonicalize_requests(conn, {"weather": [5, 1, 3, 2]}, 2)
    assert updated == 1

    records = list_requests(conn)
    assert records[0].selected_norad_ids == [1, 2]


def test_canonicalize_requests_drops_unavailable_ids(tmp_path: Path) -> None:
    db_path = tmp_path / "requests.sqlite"
    conn = init_db(db_path)

    req = RequestedLocation(
        slug="lat40p7128_lonm74p0060",
        name="NYC",
        lat=40.7128,
        lon=-74.0060,
        bundle_slug="stations",
        selected_norad_ids=[1, 4],
    )
    record = upsert_request(conn, req, precision=4)

    updated = canonicalize_requests(conn, {"stations": [1, 2, 3]}, 12)
    assert updated == 1

    records = list_requests(conn)
    assert records[0].selected_norad_ids == [1]
    assert records[0].request_key == request_key_for(
        location_slug=record.location_slug,
        bundle_slug=record.bundle_slug,
        selected_norad_ids=[1],
    )


def test_upsert_request_uses_precision_for_missing_slug(tmp_path: Path) -> None:
    db_path = tmp_path / "requests.sqlite"
    conn = init_db(db_path)

    precision = 6
    req = RequestedLocation(
        lat=47.6062,
        lon=-122.3321,
        bundle_slug="stations",
    )

    record = upsert_request(conn, req, precision=precision)
    expected_slug = compute_location_slug(47.6062, -122.3321, precision)
    assert record.location_slug == expected_slug
    expected_feed = compute_request_feed_slug(
        location_slug=expected_slug,
        bundle_slug="stations",
        selected_norad_ids=[],
    )
    assert record.request_key == expected_feed


def test_upsert_request_preserves_existing_entries(tmp_path: Path) -> None:
    db_path = tmp_path / "requests.sqlite"
    conn = init_db(db_path)

    req_one = RequestedLocation(
        lat=40.7128,
        lon=-74.0060,
        bundle_slug="stations",
    )
    req_two = RequestedLocation(
        lat=34.0522,
        lon=-118.2437,
        bundle_slug="stations",
    )

    upsert_request(conn, req_one, precision=4)
    upsert_request(conn, req_two, precision=4)

    records = list_requests(conn)
    slugs = {record.location_slug for record in records}
    assert len(records) == 2
    assert "lat40p7128_lonm74p0060" in slugs
    assert "lat34p0522_lonm118p2437" in slugs
