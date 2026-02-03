from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from skyfield import almanac
from skyfield.api import Loader, load, wgs84

from .config import Location

PLANET_TARGETS: dict[str, dict[str, str]] = {
    "mercury": {"name": "Mercury", "ephem_key": "mercury"},
    "venus": {"name": "Venus", "ephem_key": "venus"},
    "mars": {"name": "Mars", "ephem_key": "mars"},
    "jupiter": {"name": "Jupiter", "ephem_key": "jupiter barycenter"},
    "saturn": {"name": "Saturn", "ephem_key": "saturn barycenter"},
    "uranus": {"name": "Uranus", "ephem_key": "uranus barycenter"},
    "neptune": {"name": "Neptune", "ephem_key": "neptune barycenter"},
}

PLANET_ORDER = [
    "mercury",
    "venus",
    "mars",
    "jupiter",
    "saturn",
    "uranus",
    "neptune",
]

_DEFAULT_FALLBACK_WINDOW = timedelta(minutes=10)

Ephemeris = Any
SkyfieldTarget = Any
SkyfieldTopos = Any
SkyfieldTimescale = Any


@dataclass(frozen=True)
class PlanetWindow:
    rise: datetime | None
    peak: datetime
    set: datetime | None
    max_elevation_deg: float
    rise_azimuth_deg: float | None
    peak_azimuth_deg: float | None
    set_azimuth_deg: float | None
    planet: str


def _utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=timezone.utc)


def load_ephemeris(state_dir: Path, *, filename: str = "de421.bsp") -> Ephemeris:
    cache_dir = state_dir / "ephemeris"
    loader = Loader(str(cache_dir))
    return loader(filename)


def planet_time_window(window: PlanetWindow) -> tuple[datetime, datetime]:
    if window.rise and window.set:
        return window.rise, window.set
    if window.rise and not window.set:
        return window.rise, window.rise + _DEFAULT_FALLBACK_WINDOW
    if window.set and not window.rise:
        return window.set - _DEFAULT_FALLBACK_WINDOW, window.set
    return (
        window.peak - _DEFAULT_FALLBACK_WINDOW,
        window.peak + _DEFAULT_FALLBACK_WINDOW,
    )


def _alt_az(
    target: SkyfieldTarget,
    observer: SkyfieldTarget,
    ts: SkyfieldTimescale,
    at_time: datetime,
) -> tuple[float, float]:
    t = ts.from_datetime(at_time)
    astrometric = observer.at(t).observe(target)
    alt, az, _ = astrometric.apparent().altaz()
    return alt.degrees, az.degrees


def _classify_events(
    *,
    times: Iterable[datetime],
    target: SkyfieldTarget,
    observer: SkyfieldTarget,
    ts: SkyfieldTimescale,
) -> list[tuple[datetime, str]]:
    events: list[tuple[datetime, str]] = []
    epsilon = timedelta(minutes=2)
    for time_dt in times:
        before_alt, _ = _alt_az(target, observer, ts, time_dt - epsilon)
        after_alt, _ = _alt_az(target, observer, ts, time_dt + epsilon)
        if before_alt < 0 and after_alt >= 0:
            events.append((time_dt, "rise"))
        elif before_alt >= 0 and after_alt < 0:
            events.append((time_dt, "set"))
    return events


def _visibility_windows(
    *,
    events: list[tuple[datetime, str]],
    start: datetime,
    target: SkyfieldTarget,
    observer: SkyfieldTarget,
    ts: SkyfieldTimescale,
) -> list[tuple[datetime | None, datetime | None]]:
    events.sort(key=lambda item: item[0])
    start_alt, _ = _alt_az(target, observer, ts, start)
    is_up = start_alt >= 0
    current_rise: datetime | None = None
    windows: list[tuple[datetime | None, datetime | None]] = []

    for time_dt, kind in events:
        if kind == "rise":
            if not is_up:
                current_rise = time_dt
                is_up = True
        elif kind == "set":
            if is_up:
                windows.append((current_rise, time_dt))
                current_rise = None
                is_up = False

    if is_up:
        windows.append((current_rise, None))
    return windows


def _pick_transit(
    *,
    rise: datetime | None,
    set_time: datetime | None,
    transit_times: list[datetime],
) -> datetime | None:
    if rise and set_time:
        candidates = [t for t in transit_times if rise <= t <= set_time]
    elif rise and not set_time:
        candidates = [t for t in transit_times if t >= rise]
    elif set_time and not rise:
        candidates = [t for t in transit_times if t <= set_time]
    else:
        candidates = transit_times[:]
    if candidates:
        return candidates[0]
    return None


def compute_planet_windows(
    *,
    location: Location,
    start: datetime,
    end: datetime,
    planet_key: str,
    ephemeris: Ephemeris,
) -> list[PlanetWindow]:
    if planet_key not in PLANET_TARGETS:
        raise ValueError(f"Unknown planet key: {planet_key}")

    ts = load.timescale(builtin=True)
    topos = wgs84.latlon(location.lat, location.lon, elevation_m=location.elevation_m or 0)

    t0 = ts.from_datetime(_utc(start))
    t1 = ts.from_datetime(_utc(end))

    target = ephemeris[PLANET_TARGETS[planet_key]["ephem_key"]]
    observer = ephemeris["earth"] + topos

    rise_set_fn = almanac.risings_and_settings(ephemeris, target, topos)
    rs_times, _ = almanac.find_discrete(t0, t1, rise_set_fn)
    rise_set_events = _classify_events(
        times=[t.utc_datetime().replace(tzinfo=timezone.utc) for t in rs_times],
        target=target,
        observer=observer,
        ts=ts,
    )

    windows = _visibility_windows(
        events=rise_set_events,
        start=_utc(start),
        target=target,
        observer=observer,
        ts=ts,
    )

    transit_fn = almanac.meridian_transits(ephemeris, target, topos)
    transit_times, _ = almanac.find_discrete(t0, t1, transit_fn)
    transit_dt = [t.utc_datetime().replace(tzinfo=timezone.utc) for t in transit_times]

    results: list[PlanetWindow] = []
    for rise, set_time in windows:
        peak_time = _pick_transit(rise=rise, set_time=set_time, transit_times=transit_dt)
        if peak_time is None:
            if rise and set_time:
                peak_time = rise + (set_time - rise) / 2
            else:
                peak_time = _utc(start)
        peak_alt, peak_az = _alt_az(target, observer, ts, peak_time)
        rise_az = _alt_az(target, observer, ts, rise)[1] if rise else None
        set_az = _alt_az(target, observer, ts, set_time)[1] if set_time else None
        results.append(
            PlanetWindow(
                rise=rise,
                peak=peak_time,
                set=set_time,
                max_elevation_deg=peak_alt,
                rise_azimuth_deg=rise_az,
                peak_azimuth_deg=peak_az,
                set_azimuth_deg=set_az,
                planet=PLANET_TARGETS[planet_key]["name"],
            )
        )

    results.sort(key=lambda item: item.rise or item.peak)
    return results
