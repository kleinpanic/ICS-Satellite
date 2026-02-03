from pathlib import Path

import yaml

from satpass.config import load_config
from satpass.requests_db import list_requests, request_key_for
from satpass.seed import seed_requests


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
        "bundles": [
            {"slug": "popular", "name": "Popular", "norad_ids": [1, 2, 3]},
            {"slug": "stations", "name": "Stations", "celestrak_group": "stations"},
        ],
        "request_defaults": {"slug_precision_decimals": 4, "max_satellites_per_request": 12},
        "request_db_path": str(tmp_path / "requests.sqlite"),
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config_data))
    return path


def test_seed_requests_dedupes(tmp_path: Path) -> None:
    config_path = _make_config(tmp_path)
    config = load_config(config_path)
    seed_data = {
        "requests": [
            {"lat": 40.7128, "lon": -74.0060, "bundle_slug": "popular"},
            {"lat": 40.7128, "lon": -74.0060, "bundle_slug": "popular"},
        ]
    }
    seed_path = tmp_path / "seed.yaml"
    seed_path.write_text(yaml.safe_dump(seed_data))

    result = seed_requests(
        config=config,
        seed_path=seed_path,
        db_path=Path(config.request_db_path),
        reset=True,
    )

    assert result.total == 2
    assert result.inserted == 2

    conn = __import__("sqlite3").connect(config.request_db_path)
    try:
        records = list_requests(conn)
        assert len(records) == 1
    finally:
        conn.close()


def test_seed_requests_canonicalizes_explicit_full_selection(tmp_path: Path) -> None:
    config_path = _make_config(tmp_path)
    config = load_config(config_path)
    seed_data = {
        "requests": [
            {
                "lat": 47.6062,
                "lon": -122.3321,
                "bundle_slug": "popular",
                "selected_norad_ids": [1, 2, 3],
            }
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

    conn = __import__("sqlite3").connect(config.request_db_path)
    try:
        records = list_requests(conn)
        assert len(records) == 1
        expected_key = request_key_for(
            location_slug="lat47p6062_lonm122p3321",
            bundle_slug="popular",
            selected_norad_ids=[],
        )
        assert records[0].request_key == expected_key
    finally:
        conn.close()


def test_seed_requests_generates_slug_when_missing(tmp_path: Path) -> None:
    config_path = _make_config(tmp_path)
    config = load_config(config_path)
    seed_data = [
        {"lat": 47.6062, "lon": -122.3321, "bundle_slug": "popular"},
    ]
    seed_path = tmp_path / "seed.yaml"
    seed_path.write_text(yaml.safe_dump(seed_data))

    seed_requests(
        config=config,
        seed_path=seed_path,
        db_path=Path(config.request_db_path),
        reset=True,
    )

    conn = __import__("sqlite3").connect(config.request_db_path)
    try:
        records = list_requests(conn)
        assert len(records) == 1
        expected_slug = "lat47p6062_lonm122p3321"
        assert records[0].location_slug == expected_slug
    finally:
        conn.close()


def test_seed_requests_uses_provided_slug_and_sorts_ids(tmp_path: Path) -> None:
    config_path = _make_config(tmp_path)
    config = load_config(config_path)
    seed_data = {
        "requests": [
            {
                "slug": "custom-slug",
                "name": "Custom",
                "lat": 10.0,
                "lon": 20.0,
                "bundle_slug": "popular",
                "selected_norad_ids": [3, 1],
            }
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

    conn = __import__("sqlite3").connect(config.request_db_path)
    try:
        records = list_requests(conn)
        assert len(records) == 1
        assert records[0].location_slug == "custom-slug"
        assert records[0].selected_norad_ids == [1, 3]
    finally:
        conn.close()


def test_seed_writes_to_explicit_db_not_production(tmp_path: Path) -> None:
    """Seed must write to the explicitly provided DB path, not the production one."""
    config_path = _make_config(tmp_path)
    config = load_config(config_path)
    prod_db = Path(config.request_db_path)
    seed_db = tmp_path / "seed.sqlite"
    seed_data = {
        "requests": [
            {"lat": 40.7128, "lon": -74.0060, "bundle_slug": "popular"},
        ]
    }
    seed_path = tmp_path / "seed.yaml"
    seed_path.write_text(yaml.safe_dump(seed_data))

    seed_requests(
        config=config,
        seed_path=seed_path,
        db_path=seed_db,
        reset=True,
    )

    # Seed DB should have the record
    conn = __import__("sqlite3").connect(str(seed_db))
    try:
        assert len(list_requests(conn)) == 1
    finally:
        conn.close()

    # Production DB should remain untouched (empty or non-existent)
    if prod_db.exists():
        conn = __import__("sqlite3").connect(str(prod_db))
        try:
            assert len(list_requests(conn)) == 0
        finally:
            conn.close()


def test_makefile_seed_target_uses_separate_db() -> None:
    """The Makefile seed target must not write to the production DB path."""
    makefile = Path("Makefile").read_text()
    for line in makefile.splitlines():
        stripped = line.strip()
        if stripped.startswith("$(PYTHON) -m satpass seed") or stripped.startswith(
            ".venv/bin/python -m satpass seed"
        ):
            assert "--db" in stripped, "Makefile seed target must use --db to specify output path"
            assert "requests.seed.sqlite" in stripped or "seed" in stripped.split("--db")[1], (
                "Makefile seed target should write to a seed-specific DB, not the production DB"
            )


def test_production_db_has_no_seed_data() -> None:
    """The tracked production DB must not contain seed data."""
    import sqlite3

    db_path = Path("data/requests.sqlite")
    if not db_path.exists():
        return
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT COUNT(*) FROM requests WHERE requested_by = 'seed'").fetchone()
        assert rows[0] == 0, (
            f"Production DB contains {rows[0]} seed entries; "
            "run 'make reset-requests' or remove seed data"
        )
    finally:
        conn.close()


def test_seed_file_includes_expanded_bundles() -> None:
    seed_path = Path("config/seeds/seed_requests.yaml")
    seed_data = yaml.safe_load(seed_path.read_text())
    requests = seed_data.get("requests", [])
    bundles = {item.get("bundle_slug") for item in requests if isinstance(item, dict)}
    expected = {
        "galileo",
        "gnss",
        "gps-ops",
        "iss",
        "stations",
        "weather",
        "goes",
        "noaa",
        "resource",
    }
    assert expected.issubset(bundles)
