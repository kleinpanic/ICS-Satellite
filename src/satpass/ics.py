from __future__ import annotations

from datetime import datetime, timedelta, timezone

from icalendar import Calendar, Event, vDuration

from . import __version__
from .passes import PassWindow, pass_time_window
from .planets import PlanetWindow, planet_time_window

PROD_ID = f"-//satpass//{__version__}//EN"


def _fmt_time(value: datetime | None) -> str:
    if value is None:
        return "unavailable"
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _fmt_angle(value: float | None) -> str:
    if value is None:
        return "unavailable"
    return f"{value:.1f}"


def make_event_summary(pass_window: PassWindow, overhead_label_deg: float) -> str:
    label = "OVERHEAD" if pass_window.max_elevation_deg >= overhead_label_deg else "PASS"
    return f"{pass_window.sat_name} {label} (max {pass_window.max_elevation_deg:.0f} deg)"


def make_event_description(pass_window: PassWindow) -> str:
    return "\n".join(
        [
            f"Rise: {_fmt_time(pass_window.rise)}",
            f"Peak: {_fmt_time(pass_window.peak)}",
            f"Set: {_fmt_time(pass_window.set)}",
            f"Peak elevation: {pass_window.max_elevation_deg:.1f} deg",
            f"Rise azimuth: {_fmt_angle(pass_window.rise_azimuth_deg)} deg",
            f"Peak azimuth: {_fmt_angle(pass_window.peak_azimuth_deg)} deg",
            f"Set azimuth: {_fmt_angle(pass_window.set_azimuth_deg)} deg",
        ]
    )


def build_calendar(
    *,
    name: str,
    refresh_hours: int,
    events: list[Event],
) -> Calendar:
    cal = Calendar()
    cal.add("prodid", PROD_ID)
    cal.add("version", "2.0")
    cal.add("x-wr-calname", name)
    cal.add("refresh-interval", vDuration(timedelta(hours=refresh_hours)))
    cal.add("x-published-ttl", vDuration(timedelta(hours=refresh_hours)))
    for event in events:
        cal.add_component(event)
    return cal


def build_event(
    *,
    pass_window: PassWindow,
    location_slug: str,
    bundle_slug: str,
    overhead_label_deg: float,
    build_time: datetime,
) -> Event:
    start_time, end_time = pass_time_window(pass_window)
    uid_seed_time = start_time
    uid = f"{location_slug}-{bundle_slug}-{pass_window.norad_id}-{uid_seed_time:%Y%m%dT%H%M%SZ}"

    event = Event()
    event.add("uid", uid)
    event.add("dtstamp", build_time.astimezone(timezone.utc))
    event.add("dtstart", start_time.astimezone(timezone.utc))
    event.add("dtend", end_time.astimezone(timezone.utc))
    event.add("summary", make_event_summary(pass_window, overhead_label_deg))
    event.add("description", make_event_description(pass_window))
    return event


def make_planet_summary(window: PlanetWindow) -> str:
    return f"{window.planet} transit (max {window.max_elevation_deg:.0f} deg)"


def make_planet_description(window: PlanetWindow) -> str:
    return "\n".join(
        [
            f"Rise: {_fmt_time(window.rise)}",
            f"Peak: {_fmt_time(window.peak)}",
            f"Set: {_fmt_time(window.set)}",
            f"Peak elevation: {window.max_elevation_deg:.1f} deg",
            f"Rise azimuth: {_fmt_angle(window.rise_azimuth_deg)} deg",
            f"Peak azimuth: {_fmt_angle(window.peak_azimuth_deg)} deg",
            f"Set azimuth: {_fmt_angle(window.set_azimuth_deg)} deg",
        ]
    )


def build_planet_event(
    *,
    window: PlanetWindow,
    location_slug: str,
    bundle_slug: str,
    build_time: datetime,
) -> Event:
    start_time, end_time = planet_time_window(window)
    uid_seed_time = start_time
    uid = f"{location_slug}-{bundle_slug}-{window.planet}-{uid_seed_time:%Y%m%dT%H%M%SZ}"

    event = Event()
    event.add("uid", uid)
    event.add("dtstamp", build_time.astimezone(timezone.utc))
    event.add("dtstart", start_time.astimezone(timezone.utc))
    event.add("dtend", end_time.astimezone(timezone.utc))
    event.add("summary", make_planet_summary(window))
    event.add("description", make_planet_description(window))
    return event
