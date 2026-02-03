from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import Bundle, Config
from .io_utils import atomic_write_text
from .tle import TLE, fetch_tles

DEFAULT_CATALOG_LIMIT = 1000


@dataclass(frozen=True)
class CatalogResult:
    bundle_slug: str
    path: Path
    satellites_total: int
    satellites_limit: int | None
    satellites_truncated: bool


def catalog_dir(output_dir: Path) -> Path:
    return output_dir / "catalog"


def catalog_path(output_dir: Path, bundle_slug: str) -> Path:
    return catalog_dir(output_dir) / f"{bundle_slug}.json"


def catalog_is_stale(path: Path, ttl_hours: int) -> bool:
    if not path.exists():
        return True
    age = datetime.now(timezone.utc) - datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    return age >= timedelta(hours=ttl_hours)


def _resolve_catalog_limit(bundle: Bundle) -> int:
    if bundle.satellite_listing_limit is not None:
        return bundle.satellite_listing_limit
    return DEFAULT_CATALOG_LIMIT


def build_bundle_catalog(
    *,
    config: Config,
    bundle: Bundle,
    output_dir: Path,
    state_dir: Path,
) -> CatalogResult:
    tles = fetch_tles(
        cache_dir=state_dir / "tle",
        ttl_hours=config.defaults.tle_cache_hours,
        groups=[bundle.celestrak_group] if bundle.celestrak_group else [],
        norad_ids=bundle.norad_ids,
    )
    satellites = _tles_to_satellites(tles)
    total = len(satellites)
    limit = _resolve_catalog_limit(bundle)
    truncated = total > limit
    if truncated:
        satellites = satellites[:limit]

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "bundle_slug": bundle.slug,
        "bundle_name": bundle.name,
        "satellites_total": total,
        "satellites_limit": limit,
        "satellites_truncated": truncated,
        "satellites": satellites,
    }

    path = catalog_path(output_dir, bundle.slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(data, indent=2, sort_keys=True))
    return CatalogResult(
        bundle_slug=bundle.slug,
        path=path,
        satellites_total=total,
        satellites_limit=limit,
        satellites_truncated=truncated,
    )


def build_catalogs(
    *,
    config: Config,
    output_dir: Path,
    state_dir: Path,
    mode: str = "stale",
) -> list[CatalogResult]:
    results: list[CatalogResult] = []
    catalog_root = catalog_dir(output_dir)
    catalog_root.mkdir(parents=True, exist_ok=True)

    for bundle in config.bundles:
        if bundle.kind != "satellite":
            continue
        path = catalog_path(output_dir, bundle.slug)
        if mode == "stale" and not catalog_is_stale(path, config.defaults.tle_cache_hours):
            continue
        print(f"Catalog: {bundle.slug}")
        results.append(
            build_bundle_catalog(
                config=config,
                bundle=bundle,
                output_dir=output_dir,
                state_dir=state_dir,
            )
        )
    return results


def read_catalog_metadata(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return {
        "generated_at": data.get("generated_at"),
        "satellites_total": data.get("satellites_total"),
        "satellites_limit": data.get("satellites_limit"),
        "satellites_truncated": data.get("satellites_truncated"),
    }


def _tles_to_satellites(tles: list[TLE]) -> list[dict[str, object]]:
    return [{"norad_id": tle.norad_id, "name": tle.name} for tle in tles]
