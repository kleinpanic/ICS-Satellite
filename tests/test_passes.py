from datetime import datetime, timedelta, timezone
from pathlib import Path

from skyfield.api import EarthSatellite, load, wgs84

from satpass.config import Location
from satpass.passes import compute_passes, pass_time_window
from satpass.tle import TLE


def _load_tle() -> TLE:
    lines = Path("tests/fixtures/sample.tle").read_text().splitlines()
    return TLE(
        name=lines[0].strip(),
        line1=lines[1].strip(),
        line2=lines[2].strip(),
        norad_id=25544,
    )


def test_passes_sorted_and_non_overlapping() -> None:
    tle = _load_tle()
    location = Location(slug="test", name="Test", lat=47.6062, lon=-122.3321, elevation_m=0)
    start = datetime(2025, 9, 26, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    passes = compute_passes(
        tle=tle,
        location=location,
        start=start,
        end=end,
        include_if_peak_elevation_deg=10,
    )

    assert passes

    last_end = None
    for pass_window in passes:
        assert pass_window.max_elevation_deg >= 10
        start_time, end_time = pass_time_window(pass_window)
        assert start_time <= end_time
        if last_end is not None:
            assert start_time >= last_end
        last_end = end_time


def test_passes_rise_set_at_horizon() -> None:
    tle = _load_tle()
    location = Location(slug="test", name="Test", lat=47.6062, lon=-122.3321, elevation_m=0)
    start = datetime(2025, 9, 26, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    passes = compute_passes(
        tle=tle,
        location=location,
        start=start,
        end=end,
        include_if_peak_elevation_deg=10,
    )

    assert passes

    ts = load.timescale(builtin=True)
    satellite = EarthSatellite(tle.line1, tle.line2, tle.name, ts)
    topos = wgs84.latlon(location.lat, location.lon, elevation_m=location.elevation_m or 0)

    for pass_window in passes:
        if pass_window.rise is None or pass_window.set is None:
            continue
        rise_t = ts.from_datetime(pass_window.rise)
        set_t = ts.from_datetime(pass_window.set)
        rise_alt, _, _ = (satellite - topos).at(rise_t).altaz()
        set_alt, _, _ = (satellite - topos).at(set_t).altaz()
        assert abs(rise_alt.degrees) <= 0.5
        assert abs(set_alt.degrees) <= 0.5
