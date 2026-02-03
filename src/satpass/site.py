from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from . import __version__
from .catalog import read_catalog_metadata
from .config import (
    Bundle,
    Config,
    Location,
    resolve_bundle_thresholds,
    resolve_featured_locations,
)
from .io_utils import atomic_write_text
from .slug import compute_location_slug


@dataclass(frozen=True)
class FeedEntry:
    location: Location
    bundle: Bundle
    path: str
    selected_norad_ids: list[int] | None = None
    requested_at: str | None = None
    fulfilled_at: str | None = None


def copy_site_assets(output_dir: Path) -> None:
    asset_dir = Path(__file__).parent / "assets" / "site"
    output_dir.mkdir(parents=True, exist_ok=True)
    for asset in asset_dir.iterdir():
        if asset.is_file():
            target = output_dir / asset.name
            target.write_bytes(asset.read_bytes())
            shutil.copystat(asset, target)


def build_manifest(
    *,
    config: Config,
    feeds: list[FeedEntry],
    requested_feeds: list[FeedEntry] | None = None,
    generated_at: datetime,
    repo_url_override: str | None = None,
    catalog_dir: Path | None = None,
    git_sha: str | None = None,
) -> dict[str, object]:
    precision = config.request_defaults.slug_precision_decimals
    featured_locations = []
    locations_by_slug: dict[str, dict[str, object]] = {}
    for loc in resolve_featured_locations(config):
        entry = {
            "slug": loc.slug,
            "name": loc.name,
            "lat": loc.lat,
            "lon": loc.lon,
            "location_key": compute_location_slug(loc.lat, loc.lon, precision),
            "featured": True,
            "requested": False,
        }
        featured_locations.append(entry)
        locations_by_slug[loc.slug] = entry
    bundles = []
    for bundle in config.bundles:
        if bundle.kind == "satellite":
            include, overhead = resolve_bundle_thresholds(bundle, config.defaults)
        else:
            include, overhead = None, None
        catalog_meta = None
        catalog_rel_path = None
        if catalog_dir is not None and bundle.kind == "satellite":
            catalog_file = catalog_dir / f"{bundle.slug}.json"
            catalog_meta = read_catalog_metadata(catalog_file)
            if catalog_meta is not None:
                catalog_rel_path = str(catalog_file.relative_to(catalog_dir.parent))
        bundles.append(
            {
                "slug": bundle.slug,
                "name": bundle.name,
                "kind": bundle.kind,
                "planet_targets": bundle.planet_targets,
                "include_if_peak_elevation_deg": include,
                "label_overhead_if_peak_elevation_deg": overhead,
                "catalog_path": catalog_rel_path,
                "catalog_available": catalog_meta is not None,
                "catalog_generated_at": catalog_meta.get("generated_at") if catalog_meta else None,
                "satellites_total": catalog_meta.get("satellites_total") if catalog_meta else None,
                "satellites_truncated": (
                    catalog_meta.get("satellites_truncated") if catalog_meta else None
                ),
                "satellites_limit": catalog_meta.get("satellites_limit") if catalog_meta else None,
            }
        )

    feed_items_by_path: dict[str, dict[str, object]] = {}

    def _merge_feed(item: dict[str, object]) -> None:
        path = cast(str, item["path"])
        existing = feed_items_by_path.get(path)
        if not existing:
            feed_items_by_path[path] = item
            return
        merged = dict(existing)
        merged["requested"] = bool(existing.get("requested")) or bool(item.get("requested"))
        if "bundle_kind" in item and "bundle_kind" not in merged:
            merged["bundle_kind"] = item["bundle_kind"]
        if item.get("selected_norad_ids"):
            merged["selected_norad_ids"] = item["selected_norad_ids"]
        if "location_lat" in item and "location_lat" not in merged:
            merged["location_lat"] = item["location_lat"]
        if "location_lon" in item and "location_lon" not in merged:
            merged["location_lon"] = item["location_lon"]
        if "location_key" in item and "location_key" not in merged:
            merged["location_key"] = item["location_key"]
        if item.get("requested_at") and not merged.get("requested_at"):
            merged["requested_at"] = item["requested_at"]
        if item.get("fulfilled_at") and not merged.get("fulfilled_at"):
            merged["fulfilled_at"] = item["fulfilled_at"]
        feed_items_by_path[path] = merged

    for feed in feeds:
        _merge_feed(
            {
                "path": feed.path,
                "location_slug": feed.location.slug,
                "location_name": feed.location.name,
                "location_key": compute_location_slug(
                    feed.location.lat, feed.location.lon, precision
                ),
                "bundle_slug": feed.bundle.slug,
                "bundle_name": feed.bundle.name,
                "bundle_kind": feed.bundle.kind,
                "requested": False,
            }
        )

    if requested_feeds:
        for feed in requested_feeds:
            _merge_feed(
                {
                    "path": feed.path,
                    "location_slug": feed.location.slug,
                    "location_name": feed.location.name,
                    "location_lat": feed.location.lat,
                    "location_lon": feed.location.lon,
                    "location_key": compute_location_slug(
                        feed.location.lat, feed.location.lon, precision
                    ),
                    "bundle_slug": feed.bundle.slug,
                    "bundle_name": feed.bundle.name,
                    "bundle_kind": feed.bundle.kind,
                    "requested": True,
                    "selected_norad_ids": feed.selected_norad_ids,
                    "requested_at": feed.requested_at,
                    "fulfilled_at": feed.fulfilled_at,
                }
            )

    feed_items = [feed_items_by_path[path] for path in sorted(feed_items_by_path)]

    requested_locations: list[dict[str, object]] = []
    requested_last_fulfilled: dict[str, str] = {}
    if requested_feeds:
        for feed in requested_feeds:
            if not feed.fulfilled_at:
                continue
            existing = requested_last_fulfilled.get(feed.location.slug)
            if not existing or feed.fulfilled_at > existing:
                requested_last_fulfilled[feed.location.slug] = feed.fulfilled_at
    if requested_feeds:
        for feed in requested_feeds:
            slug = feed.location.slug
            if slug in locations_by_slug:
                continue
            entry = {
                "slug": slug,
                "name": feed.location.name,
                "lat": feed.location.lat,
                "lon": feed.location.lon,
                "location_key": compute_location_slug(
                    feed.location.lat, feed.location.lon, precision
                ),
                "featured": False,
                "requested": True,
            }
            last_fulfilled = requested_last_fulfilled.get(slug)
            if last_fulfilled:
                entry["last_fulfilled_at"] = last_fulfilled
            locations_by_slug[slug] = entry
            requested_locations.append(entry)

    repo_url = repo_url_override if repo_url_override else config.repo_url

    bundle_kind_counts = {"satellite": 0, "planetary": 0}
    for bundle_entry in bundles:
        kind_value = bundle_entry.get("kind")
        kind = kind_value if isinstance(kind_value, str) else "satellite"
        if kind in bundle_kind_counts:
            bundle_kind_counts[kind] += 1

    feed_kind_counts = {"satellite": 0, "planetary": 0}
    requested_feed_count = 0
    for feed_entry in feed_items:
        kind_value = feed_entry.get("bundle_kind")
        kind = kind_value if isinstance(kind_value, str) else "satellite"
        if kind in feed_kind_counts:
            feed_kind_counts[kind] += 1
        if feed_entry.get("requested"):
            requested_feed_count += 1

    last_request_fulfilled = None
    if requested_last_fulfilled:
        last_request_fulfilled = max(requested_last_fulfilled.values())

    return {
        "generated_at": generated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "build": {
            "version": __version__,
            "git_sha": git_sha,
            "built_at": generated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        "repo_url": repo_url,
        "site": {
            "title": config.site.title,
            "description": config.site.description,
        },
        "defaults": {
            "horizon_days": config.defaults.horizon_days,
            "refresh_interval_hours": config.defaults.refresh_interval_hours,
        },
        "request_defaults": {
            "slug_precision_decimals": config.request_defaults.slug_precision_decimals,
            "max_satellites_per_request": config.request_defaults.max_satellites_per_request,
            "allowlist_enabled": bool(config.allowed_requesters),
        },
        "featured_locations": featured_locations,
        "locations": featured_locations
        + sorted(requested_locations, key=lambda item: cast(str, item["name"]).lower()),
        "bundles": bundles,
        "feeds": feed_items,
        "stats": {
            "locations": {
                "featured": len(featured_locations),
                "requested": len(requested_locations),
                "total": len(featured_locations) + len(requested_locations),
            },
            "bundles": {
                "satellite": bundle_kind_counts["satellite"],
                "planetary": bundle_kind_counts["planetary"],
                "total": len(bundles),
            },
            "feeds": {
                "satellite": feed_kind_counts["satellite"],
                "planetary": feed_kind_counts["planetary"],
                "total": len(feed_items),
                "requested": requested_feed_count,
            },
            "last_request_fulfilled_at": last_request_fulfilled,
        },
    }


def write_manifest(output_dir: Path, manifest: dict[str, object]) -> None:
    feeds_dir = output_dir / "feeds"
    feeds_dir.mkdir(parents=True, exist_ok=True)
    path = feeds_dir / "index.json"
    atomic_write_text(path, json.dumps(manifest, indent=2, sort_keys=True))
