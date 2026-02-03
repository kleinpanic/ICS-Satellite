from datetime import datetime, timedelta, timezone
from pathlib import Path

from satpass.config import Location
from satpass.planets import (
    PlanetWindow,
    compute_planet_windows,
    load_ephemeris,
    planet_time_window,
)


def test_planet_time_window_fallback() -> None:
    peak = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)
    window = PlanetWindow(
        rise=None,
        peak=peak,
        set=None,
        max_elevation_deg=10.0,
        rise_azimuth_deg=None,
        peak_azimuth_deg=180.0,
        set_azimuth_deg=None,
        planet="Mars",
    )
    start, end = planet_time_window(window)
    assert start == peak - timedelta(minutes=10)
    assert end == peak + timedelta(minutes=10)


def test_compute_planet_windows_rejects_unknown_key() -> None:
    location = Location(slug="test", name="Test", lat=0, lon=0, elevation_m=0)
    start = datetime(2026, 2, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    try:
        compute_planet_windows(
            location=location,
            start=start,
            end=end,
            planet_key="pluto",
            ephemeris=None,
        )
    except ValueError as exc:
        assert "Unknown planet key" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown planet key")


def test_compute_planet_windows_smoke(ephemeris_state_dir: Path) -> None:
    ephemeris = load_ephemeris(ephemeris_state_dir)
    location = Location(slug="test", name="Test", lat=0.0, lon=0.0, elevation_m=0)
    start = datetime(2026, 2, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=2)
    windows = compute_planet_windows(
        location=location,
        start=start,
        end=end,
        planet_key="venus",
        ephemeris=ephemeris,
    )
    assert isinstance(windows, list)
    if windows:
        assert all(window.planet == "Venus" for window in windows)
