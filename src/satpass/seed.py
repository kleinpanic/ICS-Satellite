from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from .config import Config, ConfigError, RequestedLocation
from .requests_db import canonicalize_selection, default_selection, init_db, upsert_request
from .slug import compute_location_slug


class SeedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    slug: str | None = None
    lat: float
    lon: float
    elevation_m: float | None = 0
    bundle_slug: str
    selected_norad_ids: list[int] | None = None
    requested_by: str | None = "seed"
    requested_at: str | None = None


@dataclass(frozen=True)
class SeedResult:
    inserted: int
    total: int


def load_seed_requests(path: Path) -> list[SeedRequest]:
    try:
        data = yaml.safe_load(path.read_text())
    except FileNotFoundError as exc:
        raise ConfigError(f"Seed file not found: {path}") from exc
    if data is None:
        return []
    if isinstance(data, dict) and "requests" in data:
        data = data["requests"]
    if not isinstance(data, list):
        raise ConfigError("Seed file must contain a list of requests or a 'requests' list")
    requests: list[SeedRequest] = []
    for entry in data:
        try:
            requests.append(SeedRequest.model_validate(entry))
        except ValidationError as exc:
            raise ConfigError(f"Invalid seed request: {exc}") from exc
    return requests


def seed_requests(
    *,
    config: Config,
    seed_path: Path,
    db_path: Path,
    reset: bool = False,
) -> SeedResult:
    seed_requests = load_seed_requests(seed_path)
    if reset and db_path.exists():
        db_path.unlink()

    bundle_map = {bundle.slug: bundle for bundle in config.bundles}
    available_ids_map = {
        bundle.slug: bundle.norad_ids
        for bundle in config.bundles
        if bundle.kind == "satellite" and bundle.norad_ids
    }

    conn = init_db(db_path)
    inserted = 0
    try:
        for seed in seed_requests:
            bundle = bundle_map.get(seed.bundle_slug)
            if not bundle:
                raise ConfigError(f"Seed request references unknown bundle: {seed.bundle_slug}")

            slug = seed.slug
            if not slug:
                slug = compute_location_slug(
                    seed.lat, seed.lon, config.request_defaults.slug_precision_decimals
                )

            available_ids = available_ids_map.get(seed.bundle_slug, [])
            selected_ids = seed.selected_norad_ids
            if bundle.kind == "planetary":
                if selected_ids:
                    raise ConfigError("Planetary bundles cannot include selected NORAD IDs")
                selected_ids = []
                canonical_selected = []
            else:
                if not selected_ids:
                    selected_ids = default_selection(
                        available_ids, config.request_defaults.max_satellites_per_request
                    )
                max_sats = config.request_defaults.max_satellites_per_request
                if selected_ids and len(selected_ids) > max_sats:
                    selected_ids = selected_ids[:max_sats]
                canonical_selected = canonicalize_selection(selected_ids, available_ids)

            request = RequestedLocation(
                slug=slug,
                name=seed.name,
                lat=seed.lat,
                lon=seed.lon,
                elevation_m=seed.elevation_m,
                bundle_slug=seed.bundle_slug,
                selected_norad_ids=canonical_selected,
                requested_by=seed.requested_by,
                requested_at=seed.requested_at,
            )
            upsert_request(
                conn,
                request,
                precision=config.request_defaults.slug_precision_decimals,
            )
            inserted += 1
    finally:
        conn.close()

    return SeedResult(inserted=inserted, total=len(seed_requests))
