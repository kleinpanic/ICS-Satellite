from __future__ import annotations

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from icalendar import Event

from .config import (
    Bundle,
    Config,
    Location,
    resolve_bundle_thresholds,
    resolve_featured_bundles,
    resolve_featured_locations,
    resolve_repo_url,
)
from .ics import build_calendar, build_event, build_planet_event
from .io_utils import atomic_write_bytes
from .passes import compute_passes
from .planets import PLANET_ORDER, compute_planet_windows, load_ephemeris
from .requests_db import (
    canonicalize_requests,
    canonicalize_selection,
    dedupe_requests_by_signature,
    ensure_location_keys,
    init_db,
    load_requests_from_db,
    migrate_yaml_requests,
)
from .site import FeedEntry, build_manifest, copy_site_assets, write_manifest
from .slug import compute_request_feed_slug
from .tle import TLE, fetch_tles


@dataclass(frozen=True)
class FeedBuildResult:
    path: Path
    feed_entry: FeedEntry


def _build_events(
    *,
    location: Location,
    bundle: Bundle,
    tles: list[TLE],
    include_if_peak_elevation_deg: float,
    overhead_label_deg: float,
    start: datetime,
    end: datetime,
    build_time: datetime,
) -> list[Event]:
    events: list[Event] = []

    def build_for_tle(tle: TLE) -> list[Event]:
        tle_events: list[Event] = []
        passes = compute_passes(
            tle=tle,
            location=location,
            start=start,
            end=end,
            include_if_peak_elevation_deg=include_if_peak_elevation_deg,
        )
        for pass_window in passes:
            if pass_window.max_elevation_deg < include_if_peak_elevation_deg:
                continue
            tle_events.append(
                build_event(
                    pass_window=pass_window,
                    location_slug=location.slug,
                    bundle_slug=bundle.slug,
                    overhead_label_deg=overhead_label_deg,
                    build_time=build_time,
                )
            )
        return tle_events

    if len(tles) > 1:
        max_workers = min(4, len(tles))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for tle_events in executor.map(build_for_tle, tles):
                events.extend(tle_events)
    else:
        for tle in tles:
            events.extend(build_for_tle(tle))
    events.sort(key=lambda event: event.decoded("dtstart"))
    return events


def _build_planet_events(
    *,
    location: Location,
    bundle: Bundle,
    ephemeris: object,
    start: datetime,
    end: datetime,
    build_time: datetime,
) -> list[Event]:
    events: list[Event] = []
    targets = bundle.planet_targets or []
    ordered_targets = [key for key in PLANET_ORDER if key in targets] + [
        key for key in targets if key not in PLANET_ORDER
    ]
    for planet_key in ordered_targets:
        windows = compute_planet_windows(
            location=location,
            start=start,
            end=end,
            planet_key=planet_key,
            ephemeris=ephemeris,
        )
        for window in windows:
            events.append(
                build_planet_event(
                    window=window,
                    location_slug=location.slug,
                    bundle_slug=bundle.slug,
                    build_time=build_time,
                )
            )
    events.sort(key=lambda event: event.decoded("dtstart"))
    return events


def _resolve_git_sha() -> str | None:
    for key in ("SATPASS_GIT_SHA", "GITHUB_SHA"):
        value = os.environ.get(key)
        if value:
            return value
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return output.strip()
    except Exception:
        return None


def build_feed(
    *,
    output_dir: Path,
    location: Location,
    bundle: Bundle,
    tles: list[TLE],
    include_if_peak_elevation_deg: float,
    overhead_label_deg: float,
    refresh_interval_hours: int,
    start: datetime,
    end: datetime,
    build_time: datetime,
    feed_slug: str | None = None,
    selected_norad_ids: list[int] | None = None,
) -> FeedBuildResult:
    events = _build_events(
        location=location,
        bundle=bundle,
        tles=tles,
        include_if_peak_elevation_deg=include_if_peak_elevation_deg,
        overhead_label_deg=overhead_label_deg,
        start=start,
        end=end,
        build_time=build_time,
    )

    name = f"{location.name} - {bundle.name}"
    calendar = build_calendar(name=name, refresh_hours=refresh_interval_hours, events=events)

    feeds_dir = output_dir / "feeds"
    feeds_dir.mkdir(parents=True, exist_ok=True)
    slug = feed_slug or f"{location.slug}--{bundle.slug}"
    filename = f"{slug}.ics"
    path = feeds_dir / filename
    atomic_write_bytes(path, calendar.to_ical())

    return FeedBuildResult(
        path=path,
        feed_entry=FeedEntry(
            location=location,
            bundle=bundle,
            path=f"feeds/{filename}",
            selected_norad_ids=selected_norad_ids,
        ),
    )


def build_all(
    config: Config,
    output_dir: Path,
    state_dir: Path,
    requests_dir: Path | None = None,
) -> list[FeedEntry]:
    output_dir.mkdir(parents=True, exist_ok=True)
    copy_site_assets(output_dir)

    build_time = datetime.now(timezone.utc)
    start = build_time
    end = build_time + timedelta(days=config.defaults.horizon_days)

    feeds: list[FeedEntry] = []
    requested_feeds: list[FeedEntry] = []
    bundle_thresholds: dict[str, tuple[float, float]] = {}
    bundle_tles: dict[str, list[TLE]] = {}
    bundle_available_ids: dict[str, list[int]] = {}

    featured_locations = resolve_featured_locations(config)
    featured_bundles = resolve_featured_bundles(config)
    bundle_map = {bundle.slug: bundle for bundle in config.bundles}

    # Load requests (without canonicalization) to determine bundle needs
    if requests_dir is None:
        requests_dir = Path("config/requests")
    db_path = Path(config.request_db_path)
    conn = init_db(db_path)
    try:
        migrate_yaml_requests(config=config, conn=conn, requests_dir=requests_dir)
        ensure_location_keys(conn, config.request_defaults.slug_precision_decimals)
        dedupe_requests_by_signature(conn, config.request_defaults.slug_precision_decimals)
        requests = load_requests_from_db(conn)
    finally:
        conn.close()

    requested_bundle_slugs = {req.bundle_slug for req in requests}
    bundles_needed = {bundle.slug for bundle in featured_bundles} | requested_bundle_slugs
    bundles_to_fetch = [bundle_map[slug] for slug in sorted(bundles_needed) if slug in bundle_map]

    # Fetch TLEs once per needed satellite bundle
    for bundle in bundles_to_fetch:
        if bundle.kind != "satellite":
            continue
        include, overhead = resolve_bundle_thresholds(bundle, config.defaults)
        bundle_thresholds[bundle.slug] = (include, overhead)
        print(f"TLE: {bundle.slug}")
        tles = fetch_tles(
            cache_dir=state_dir / "tle",
            ttl_hours=config.defaults.tle_cache_hours,
            groups=[bundle.celestrak_group] if bundle.celestrak_group else [],
            norad_ids=bundle.norad_ids,
        )
        bundle_tles[bundle.slug] = tles
        bundle_available_ids[bundle.slug] = [tle.norad_id for tle in tles]

    ephemeris = None
    if any(bundle.kind == "planetary" for bundle in bundles_to_fetch):
        print("Ephemeris: planets")
        ephemeris = load_ephemeris(state_dir)

    # Build feeds for featured locations (if configured)
    if featured_bundles and featured_locations:
        print("Build: featured feeds")
    for bundle in featured_bundles:
        for location in featured_locations:
            if bundle.kind == "planetary":
                if ephemeris is None:
                    raise ValueError("Planetary bundle requested without ephemeris loaded")
                events = _build_planet_events(
                    location=location,
                    bundle=bundle,
                    ephemeris=ephemeris,
                    start=start,
                    end=end,
                    build_time=build_time,
                )
                name = f"{location.name} - {bundle.name}"
                calendar = build_calendar(
                    name=name,
                    refresh_hours=config.defaults.refresh_interval_hours,
                    events=events,
                )
                feeds_dir = output_dir / "feeds"
                feeds_dir.mkdir(parents=True, exist_ok=True)
                slug = f"{location.slug}--{bundle.slug}"
                filename = f"{slug}.ics"
                path = feeds_dir / filename
                atomic_write_bytes(path, calendar.to_ical())
                feeds.append(
                    FeedEntry(
                        location=location,
                        bundle=bundle,
                        path=f"feeds/{filename}",
                    )
                )
                continue
            include, overhead = bundle_thresholds[bundle.slug]
            tles = bundle_tles[bundle.slug]
            result = build_feed(
                output_dir=output_dir,
                location=location,
                bundle=bundle,
                tles=tles,
                include_if_peak_elevation_deg=include,
                overhead_label_deg=overhead,
                refresh_interval_hours=config.defaults.refresh_interval_hours,
                start=start,
                end=end,
                build_time=build_time,
            )
            feeds.append(result.feed_entry)

    # Canonicalize requests now that we have bundle availability, then reload
    conn = init_db(db_path)
    try:
        canonicalize_requests(
            conn,
            bundle_available_ids,
            config.request_defaults.max_satellites_per_request,
        )
        dedupe_requests_by_signature(conn, config.request_defaults.slug_precision_decimals)
        requests = load_requests_from_db(conn)
    finally:
        conn.close()

    if requests:
        print("Build: requested feeds")
    for req in requests:
        bundle = bundle_map[req.bundle_slug]
        location = req.to_location(precision=config.request_defaults.slug_precision_decimals)
        if bundle.kind == "planetary":
            if ephemeris is None:
                raise ValueError("Planetary bundle requested without ephemeris loaded")
            if req.selected_norad_ids:
                raise ValueError("Planetary bundles cannot include selected NORAD IDs")
            feed_slug = compute_request_feed_slug(
                location_slug=location.slug,
                bundle_slug=bundle.slug,
                selected_norad_ids=[],
            )
            events = _build_planet_events(
                location=location,
                bundle=bundle,
                ephemeris=ephemeris,
                start=start,
                end=end,
                build_time=build_time,
            )
            name = f"{location.name} - {bundle.name}"
            calendar = build_calendar(
                name=name,
                refresh_hours=config.defaults.refresh_interval_hours,
                events=events,
            )
            feeds_dir = output_dir / "feeds"
            feeds_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{feed_slug}.ics"
            path = feeds_dir / filename
            atomic_write_bytes(path, calendar.to_ical())
            requested_feeds.append(
                FeedEntry(
                    location=location,
                    bundle=bundle,
                    path=f"feeds/{filename}",
                    requested_at=req.requested_at,
                    fulfilled_at=build_time.astimezone(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                )
            )
            continue
        include, overhead = bundle_thresholds[bundle.slug]
        tles = bundle_tles[bundle.slug]
        selected_ids = canonicalize_selection(
            req.selected_norad_ids,
            bundle_available_ids.get(bundle.slug, []),
        )
        if selected_ids and len(selected_ids) > config.request_defaults.max_satellites_per_request:
            raise ValueError(
                f"Requested {len(selected_ids)} satellites exceeds max "
                f"{config.request_defaults.max_satellites_per_request}"
            )
        if selected_ids:
            available_ids = {tle.norad_id for tle in tles}
            missing = [norad_id for norad_id in selected_ids if norad_id not in available_ids]
            if missing:
                raise ValueError(f"Requested NORAD IDs not in bundle {bundle.slug}: {missing}")
            tles = [tle for tle in tles if tle.norad_id in selected_ids]

        feed_slug = compute_request_feed_slug(
            location_slug=location.slug,
            bundle_slug=bundle.slug,
            selected_norad_ids=selected_ids,
        )
        result = build_feed(
            output_dir=output_dir,
            location=location,
            bundle=bundle,
            tles=tles,
            include_if_peak_elevation_deg=include,
            overhead_label_deg=overhead,
            refresh_interval_hours=config.defaults.refresh_interval_hours,
            start=start,
            end=end,
            build_time=build_time,
            feed_slug=feed_slug,
            selected_norad_ids=selected_ids,
        )
        requested_feeds.append(
            FeedEntry(
                location=result.feed_entry.location,
                bundle=result.feed_entry.bundle,
                path=result.feed_entry.path,
                selected_norad_ids=result.feed_entry.selected_norad_ids,
                requested_at=req.requested_at,
                fulfilled_at=build_time.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            )
        )

    # Resolve repo URL (handles placeholder)
    effective_repo_url = resolve_repo_url(config)

    manifest = build_manifest(
        config=config,
        feeds=feeds,
        requested_feeds=requested_feeds,
        generated_at=build_time,
        repo_url_override=effective_repo_url,
        catalog_dir=output_dir / "catalog",
        git_sha=_resolve_git_sha(),
    )
    write_manifest(output_dir, manifest)
    return feeds + requested_feeds
