from datetime import datetime, timezone

from satpass import __version__
from satpass.ics import build_calendar, build_event
from satpass.passes import PassWindow


def test_ics_contains_required_fields() -> None:
    pass_window = PassWindow(
        rise=datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
        peak=datetime(2025, 1, 1, 0, 5, tzinfo=timezone.utc),
        set=datetime(2025, 1, 1, 0, 10, tzinfo=timezone.utc),
        max_elevation_deg=67.2,
        rise_azimuth_deg=10.0,
        peak_azimuth_deg=180.0,
        set_azimuth_deg=250.0,
        sat_name="ISS",
        norad_id=25544,
    )
    build_time = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
    event = build_event(
        pass_window=pass_window,
        location_slug="seattle",
        bundle_slug="stations",
        overhead_label_deg=80,
        build_time=build_time,
    )
    cal = build_calendar(name="Test", refresh_hours=6, events=[event])
    ical = cal.to_ical().decode("utf-8")

    assert "BEGIN:VCALENDAR" in ical
    assert f"PRODID:-//satpass//{__version__}//EN" in ical
    assert "UID:seattle-stations-25544-20250101T000000Z" in ical
    assert "SUMMARY:ISS PASS (max 67 deg)" in ical
