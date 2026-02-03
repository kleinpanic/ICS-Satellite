from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from skyfield.api import EarthSatellite, load, wgs84

from .config import Location
from .tle import TLE


@dataclass(frozen=True)
class PassWindow:
    rise: datetime | None
    peak: datetime
    set: datetime | None
    max_elevation_deg: float
    rise_azimuth_deg: float | None
    peak_azimuth_deg: float | None
    set_azimuth_deg: float | None
    sat_name: str
    norad_id: int


class PassError(RuntimeError):
    pass


_DEFAULT_FALLBACK_WINDOW = timedelta(minutes=10)


def _utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=timezone.utc)


def _group_events(
    times: Iterable[datetime],
    events: Iterable[int],
) -> list[tuple[datetime | None, list[datetime], datetime | None]]:
    passes: list[tuple[datetime | None, list[datetime], datetime | None]] = []
    rise_time: datetime | None = None
    peaks: list[datetime] = []
    set_time: datetime | None = None

    def finalize() -> None:
        nonlocal rise_time, peaks, set_time
        if peaks:
            passes.append((rise_time, peaks[:], set_time))
        rise_time = None
        peaks = []
        set_time = None

    for time_dt, event in zip(times, events):
        if event == 0:
            if rise_time is not None or peaks or set_time is not None:
                finalize()
            rise_time = time_dt
        elif event == 1:
            if rise_time is None and not peaks:
                rise_time = None
            peaks.append(time_dt)
        elif event == 2:
            set_time = time_dt
            finalize()
    if rise_time is not None or peaks or set_time is not None:
        finalize()
    return passes


def compute_passes(
    *,
    tle: TLE,
    location: Location,
    start: datetime,
    end: datetime,
    include_if_peak_elevation_deg: float,
) -> list[PassWindow]:
    ts = load.timescale(builtin=True)
    satellite = EarthSatellite(tle.line1, tle.line2, tle.name, ts)
    topos = wgs84.latlon(location.lat, location.lon, elevation_m=location.elevation_m or 0)

    t0 = ts.from_datetime(_utc(start))
    t1 = ts.from_datetime(_utc(end))

    times, events = satellite.find_events(
        topos,
        t0,
        t1,
        altitude_degrees=0,
    )

    utc_times = [t.utc_datetime().replace(tzinfo=timezone.utc) for t in times]
    grouped = _group_events(utc_times, events)

    def alt_az(at_time: datetime) -> tuple[float, float]:
        t = ts.from_datetime(at_time)
        topocentric = (satellite - topos).at(t)
        alt, az, _ = topocentric.altaz()
        return alt.degrees, az.degrees

    passes: list[PassWindow] = []
    for rise, peaks, set_time in grouped:
        peak_altitudes = [(alt_az(peak)[0], peak) for peak in peaks]
        if not peak_altitudes:
            continue
        max_elevation_deg, peak_time = max(peak_altitudes, key=lambda item: item[0])
        if max_elevation_deg < include_if_peak_elevation_deg:
            continue
        rise_az = alt_az(rise)[1] if rise else None
        peak_az = alt_az(peak_time)[1]
        set_az = alt_az(set_time)[1] if set_time else None
        passes.append(
            PassWindow(
                rise=rise,
                peak=peak_time,
                set=set_time,
                max_elevation_deg=max_elevation_deg,
                rise_azimuth_deg=rise_az,
                peak_azimuth_deg=peak_az,
                set_azimuth_deg=set_az,
                sat_name=tle.name,
                norad_id=tle.norad_id,
            )
        )

    passes.sort(key=lambda item: item.rise or item.peak)
    return passes


def pass_time_window(pass_window: PassWindow) -> tuple[datetime, datetime]:
    if pass_window.rise and pass_window.set:
        return pass_window.rise, pass_window.set
    if pass_window.rise and not pass_window.set:
        return pass_window.rise, pass_window.rise + _DEFAULT_FALLBACK_WINDOW
    if pass_window.set and not pass_window.rise:
        return pass_window.set - _DEFAULT_FALLBACK_WINDOW, pass_window.set
    return (
        pass_window.peak - _DEFAULT_FALLBACK_WINDOW,
        pass_window.peak + _DEFAULT_FALLBACK_WINDOW,
    )
