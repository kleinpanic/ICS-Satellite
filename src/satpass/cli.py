from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__
from .build import build_all
from .catalog import build_catalogs
from .config import (
    Config,
    ConfigError,
    Location,
    load_config,
    resolve_bundle_thresholds,
    resolve_featured_locations,
)
from .passes import compute_passes, pass_time_window
from .planets import compute_planet_windows, load_ephemeris, planet_time_window
from .requests_db import ensure_db_loaded, init_db, list_requests
from .seed import seed_requests
from .slug import compute_location_slug
from .tle import fetch_tles


def _error(message: str) -> None:
    print(message, file=sys.stderr)


def _slugify(name: str) -> str:
    slug = []
    for ch in name.strip().lower():
        if ch.isalnum():
            slug.append(ch)
        elif ch in {" ", "-", "_"}:
            if slug and slug[-1] != "-":
                slug.append("-")
    return "".join(slug).strip("-")


def _load_config_or_exit(config_path: Path) -> Config:
    try:
        return load_config(config_path)
    except ConfigError as exc:
        _error(str(exc))
        raise SystemExit(2) from exc


def cmd_validate(args: argparse.Namespace) -> None:
    _load_config_or_exit(Path(args.config))
    print("Config OK")


def cmd_build(args: argparse.Namespace) -> None:
    config = _load_config_or_exit(Path(args.config))
    output_dir = Path(args.out)
    state_dir = Path("state")
    requests_dir = Path(args.requests) if args.requests else Path("config/requests")
    if args.catalog != "none":
        build_catalogs(
            config=config,
            output_dir=output_dir,
            state_dir=state_dir,
            mode=args.catalog,
        )
    build_all(config, output_dir, state_dir, requests_dir)
    print(f"Build complete: {output_dir}")


def cmd_preview(args: argparse.Namespace) -> None:
    config = _load_config_or_exit(Path(args.config))
    bundle = next((b for b in config.bundles if b.slug == args.bundle), None)
    if not bundle:
        _error(f"Unknown bundle slug: {args.bundle}")
        raise SystemExit(2)

    location = None
    if args.lat is not None or args.lon is not None:
        if args.lat is None or args.lon is None:
            _error("Both --lat and --lon are required when using custom coordinates.")
            raise SystemExit(2)
        slug = compute_location_slug(
            args.lat, args.lon, config.request_defaults.slug_precision_decimals
        )
        location = Location(
            slug=slug,
            name=args.name or f"Custom ({args.lat}, {args.lon})",
            lat=args.lat,
            lon=args.lon,
            elevation_m=args.elevation_m,
        )
    else:
        if not args.location:
            _error("Either --location or --lat/--lon is required.")
            raise SystemExit(2)
        featured_locations = resolve_featured_locations(config)
        location = next((loc for loc in featured_locations if loc.slug == args.location), None)
        if not location:
            requests = ensure_db_loaded(
                config=config,
                db_path=Path(config.request_db_path),
                requests_dir=Path(args.requests) if args.requests else Path("config/requests"),
            )
            requested = next((loc for loc in requests if loc.slug == args.location), None)
            if requested:
                location = requested.to_location(
                    precision=config.request_defaults.slug_precision_decimals
                )
        if not location:
            _error(f"Unknown location slug: {args.location}")
            raise SystemExit(2)

    start = datetime.now(timezone.utc)
    end = start + timedelta(days=args.days)

    lines: list[tuple[datetime, str]] = []
    if bundle.kind == "planetary":
        ephemeris = load_ephemeris(Path("state"))
        for planet_key in bundle.planet_targets or []:
            windows = compute_planet_windows(
                location=location,
                start=start,
                end=end,
                planet_key=planet_key,
                ephemeris=ephemeris,
            )
            for window in windows:
                start_time, end_time = planet_time_window(window)
                lines.append(
                    (
                        start_time,
                        (
                            f"{window.planet} | {start_time:%Y-%m-%d %H:%M} -> "
                            f"{end_time:%Y-%m-%d %H:%M} UTC | "
                            f"max {window.max_elevation_deg:.1f} deg"
                        ),
                    )
                )
    else:
        include, _ = resolve_bundle_thresholds(bundle, config.defaults)
        tles = fetch_tles(
            cache_dir=Path("state") / "tle",
            ttl_hours=config.defaults.tle_cache_hours,
            groups=[bundle.celestrak_group] if bundle.celestrak_group else [],
            norad_ids=bundle.norad_ids,
        )
        for tle in tles:
            passes = compute_passes(
                tle=tle,
                location=location,
                start=start,
                end=end,
                include_if_peak_elevation_deg=include,
            )
            for pass_window in passes:
                start_time, end_time = pass_time_window(pass_window)
                lines.append(
                    (
                        start_time,
                        (
                            f"{pass_window.sat_name} | {start_time:%Y-%m-%d %H:%M} -> "
                            f"{end_time:%Y-%m-%d %H:%M} UTC | "
                            f"max {pass_window.max_elevation_deg:.1f} deg"
                        ),
                    )
                )
    for _, line in sorted(lines, key=lambda item: item[0]):
        print(line)


def cmd_add_location(args: argparse.Namespace) -> None:
    slug = args.slug or _slugify(args.name)
    snippet = (
        '- slug: "{slug}"\n  name: "{name}"\n  lat: {lat}\n  lon: {lon}\n  elevation_m: {elev}\n'
    ).format(
        slug=slug,
        name=args.name,
        lat=args.lat,
        lon=args.lon,
        elev=args.elevation_m,
    )
    print("Add this snippet under locations:")
    print(snippet)


def cmd_seed(args: argparse.Namespace) -> None:
    config = _load_config_or_exit(Path(args.config))
    seed_path = Path(args.seed)
    db_path = Path(args.db) if args.db else Path(config.request_db_path)
    result = seed_requests(config=config, seed_path=seed_path, db_path=db_path, reset=args.reset)
    print(f"Seeded {result.inserted} requests into {db_path}")


def cmd_reset_requests(args: argparse.Namespace) -> None:
    if not args.yes:
        _error("Refusing to reset requests without --yes.")
        raise SystemExit(2)

    config = _load_config_or_exit(Path(args.config))
    db_path = Path(args.db) if args.db else Path(config.request_db_path)
    requests_dir = Path(args.requests) if args.requests else Path("config/requests")
    output_dir = Path(args.out) if args.out else Path("site")

    request_keys: list[str] = []
    if db_path.exists():
        conn = init_db(db_path)
        try:
            request_keys = [record.request_key for record in list_requests(conn)]
        finally:
            conn.close()
        db_path.unlink()

    if requests_dir.exists():
        for path in requests_dir.glob("*.yaml"):
            path.unlink()

    feeds_dir = output_dir / "feeds"
    if request_keys and feeds_dir.exists():
        for key in request_keys:
            feed_path = feeds_dir / f"{key}.ics"
            if feed_path.exists():
                feed_path.unlink()

    print("Reset complete: requested feeds cleared. Rebuild to restore featured feeds.")


def cmd_catalog_build(args: argparse.Namespace) -> None:
    config = _load_config_or_exit(Path(args.config))
    output_dir = Path(args.out)
    state_dir = Path("state")
    build_catalogs(
        config=config,
        output_dir=output_dir,
        state_dir=state_dir,
        mode=args.mode,
    )
    print(f"Catalog build complete: {output_dir / 'catalog'}")


def cmd_version(_: argparse.Namespace) -> None:
    print(f"satpass {__version__}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="satpass")
    parser.add_argument("--version", action="version", version=f"satpass {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    build = subparsers.add_parser("build")
    build.add_argument("--config", required=True)
    build.add_argument("--out", required=True)
    build.add_argument("--requests", default=None, help="Path to requests directory")
    build.add_argument(
        "--catalog",
        default="none",
        choices=["none", "stale", "all"],
        help="Build bundle catalogs before the main build",
    )
    build.set_defaults(func=cmd_build)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--config", required=True)
    validate.set_defaults(func=cmd_validate)

    preview = subparsers.add_parser("preview")
    preview.add_argument("--config", required=True)
    preview.add_argument("--location")
    preview.add_argument("--lat", type=float)
    preview.add_argument("--lon", type=float)
    preview.add_argument("--name")
    preview.add_argument("--elevation-m", type=float, default=0, dest="elevation_m")
    preview.add_argument("--requests", default=None, help="Path to requests directory")
    preview.add_argument("--bundle", required=True)
    preview.add_argument("--days", type=int, default=3)
    preview.set_defaults(func=cmd_preview)

    add_loc = subparsers.add_parser("add-location")
    add_loc.add_argument("--name", required=True)
    add_loc.add_argument("--slug")
    add_loc.add_argument("--lat", type=float, required=True)
    add_loc.add_argument("--lon", type=float, required=True)
    add_loc.add_argument("--elevation-m", type=float, default=0, dest="elevation_m")
    add_loc.set_defaults(func=cmd_add_location)

    seed = subparsers.add_parser("seed")
    seed.add_argument("--config", required=True)
    seed.add_argument("--seed", required=True)
    seed.add_argument("--db", default=None)
    seed.add_argument("--reset", action="store_true")
    seed.set_defaults(func=cmd_seed)

    reset_requests = subparsers.add_parser("reset-requests")
    reset_requests.add_argument("--config", required=True)
    reset_requests.add_argument("--db", default=None)
    reset_requests.add_argument("--requests", default=None)
    reset_requests.add_argument("--out", default=None)
    reset_requests.add_argument("--yes", action="store_true")
    reset_requests.set_defaults(func=cmd_reset_requests)

    catalog = subparsers.add_parser("catalog")
    catalog_sub = catalog.add_subparsers(dest="catalog_command")
    catalog_build = catalog_sub.add_parser("build")
    catalog_build.add_argument("--config", required=True)
    catalog_build.add_argument("--out", required=True)
    catalog_build.add_argument("--mode", choices=["stale", "all"], default="stale")
    catalog_build.set_defaults(func=cmd_catalog_build)

    version = subparsers.add_parser("version")
    version.set_defaults(func=cmd_version)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        raise SystemExit(1)
    args.func(args)


if __name__ == "__main__":
    main()
