from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .slug import compute_location_slug

SLUG_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789-_"
DEFAULT_REPO_URL_PLACEHOLDER = "https://github.com/your-user/your-repo"


def _is_slug(value: str) -> bool:
    return value != "" and all(ch in SLUG_CHARS for ch in value)


class Defaults(BaseModel):
    model_config = ConfigDict(extra="forbid")
    horizon_days: int = Field(ge=1)
    tle_cache_hours: int = Field(ge=1)
    refresh_interval_hours: int = Field(ge=1)
    include_if_peak_elevation_deg: float = Field(ge=0, le=90)
    label_overhead_if_peak_elevation_deg: float = Field(ge=0, le=90)

    @model_validator(mode="after")
    def check_thresholds(self) -> "Defaults":
        if self.label_overhead_if_peak_elevation_deg < self.include_if_peak_elevation_deg:
            raise ValueError(
                "label_overhead_if_peak_elevation_deg must be >= include_if_peak_elevation_deg"
            )
        return self


class SiteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    description: str


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str
    name: str
    lat: float
    lon: float
    elevation_m: float | None = 0

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        if not _is_slug(value):
            raise ValueError("slug must be lowercase letters, numbers, or dashes")
        return value

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, value: float) -> float:
        if not -90 <= value <= 90:
            raise ValueError("lat must be between -90 and 90")
        return value

    @field_validator("lon")
    @classmethod
    def validate_lon(cls, value: float) -> float:
        if not -180 <= value <= 180:
            raise ValueError("lon must be between -180 and 180")
        return value


class Bundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str
    name: str
    kind: str = "satellite"
    celestrak_group: str | None = None
    norad_ids: list[int] = Field(default_factory=list)
    include_if_peak_elevation_deg: float | None = Field(default=None, ge=0, le=90)
    label_overhead_if_peak_elevation_deg: float | None = Field(default=None, ge=0, le=90)
    satellite_listing_limit: int | None = Field(default=None, ge=1)
    planet_targets: list[str] | None = None

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        if not _is_slug(value):
            raise ValueError("slug must be lowercase letters, numbers, or dashes")
        return value

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, value: str) -> str:
        if value not in {"satellite", "planetary"}:
            raise ValueError("bundle kind must be 'satellite' or 'planetary'")
        return value

    @model_validator(mode="after")
    def validate_bundle_kind(self) -> "Bundle":
        if self.kind == "planetary":
            if self.celestrak_group or self.norad_ids:
                raise ValueError("planetary bundles cannot define celestrak_group or norad_ids")
            if not self.planet_targets:
                raise ValueError("planetary bundles require planet_targets")
        else:
            if self.planet_targets:
                raise ValueError("satellite bundles cannot define planet_targets")
        return self

    @model_validator(mode="after")
    def check_sources(self) -> "Bundle":
        if self.kind == "planetary":
            return self
        if not self.celestrak_group and not self.norad_ids:
            raise ValueError("bundle must include celestrak_group and/or norad_ids")
        if self.norad_ids and any(norad <= 0 for norad in self.norad_ids):
            raise ValueError("norad_ids must be positive integers")
        return self


class RequestDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug_precision_decimals: int = Field(default=4, ge=1, le=8)
    # TODO: request_defaults.horizon_days is currently unused.
    horizon_days: int | None = None
    max_satellites_per_request: int = Field(default=12, ge=1, le=200)


class RequestedLocation(BaseModel):
    """A location requested through the IssueOps pipeline."""

    model_config = ConfigDict(extra="forbid")
    slug: str | None = None
    name: str | None = None
    lat: float
    lon: float
    elevation_m: float | None = 0
    bundle_slug: str
    selected_norad_ids: list[int] | None = None
    requested_by: str | None = None
    requested_at: str | None = None

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, value: float) -> float:
        if not -90 <= value <= 90:
            raise ValueError("lat must be between -90 and 90")
        return value

    @field_validator("lon")
    @classmethod
    def validate_lon(cls, value: float) -> float:
        if not -180 <= value <= 180:
            raise ValueError("lon must be between -180 and 180")
        return value

    @field_validator("selected_norad_ids")
    @classmethod
    def validate_selected_norad_ids(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if not value:
            return []
        for norad_id in value:
            if norad_id <= 0:
                raise ValueError("selected_norad_ids must be positive integers")
        return value

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not _is_slug(value):
            raise ValueError("slug must be lowercase letters, numbers, or dashes")
        return value

    def resolved_location_slug(self, *, precision: int) -> str:
        slug = self.slug
        if not slug:
            return compute_location_slug(self.lat, self.lon, precision)
        if "--" not in slug:
            return slug
        return slug.split("--")[0]

    def to_location(self, *, precision: int) -> Location:
        """Convert to a Location instance for feed generation."""
        name = self.name or f"Custom ({self.lat}, {self.lon})"
        location_slug = self.resolved_location_slug(precision=precision)
        return Location(
            slug=location_slug,
            name=name,
            lat=self.lat,
            lon=self.lon,
            elevation_m=self.elevation_m,
        )


class Config(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int
    repo_url: str
    site: SiteConfig
    defaults: Defaults
    featured_locations: list[Location] = Field(default_factory=list)
    locations: list[Location] | None = None
    bundles: list[Bundle]
    featured_bundles: list[str] | None = None
    allowed_requesters: list[str] = Field(default_factory=list)
    request_defaults: RequestDefaults = Field(default_factory=RequestDefaults)
    request_db_path: str = "data/requests.sqlite"

    @model_validator(mode="after")
    def check_uniques(self) -> "Config":
        _ensure_unique("location", (loc.slug for loc in resolve_featured_locations(self)))
        _ensure_unique("bundle", (bundle.slug for bundle in self.bundles))
        if self.featured_bundles is not None:
            bundle_slugs = {bundle.slug for bundle in self.bundles}
            unknown = [slug for slug in self.featured_bundles if slug not in bundle_slugs]
            if unknown:
                raise ValueError(f"featured_bundles contains unknown bundle slugs: {unknown}")
        return self


class ConfigError(RuntimeError):
    pass


def _ensure_unique(kind: str, values: Iterable[str]) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"duplicate {kind} slug: {value}")
        seen.add(value)


def load_config(path: Path) -> Config:
    try:
        data = yaml.safe_load(path.read_text())
    except FileNotFoundError as exc:
        raise ConfigError(f"Config file not found: {path}") from exc
    if data is None:
        raise ConfigError(f"Config file is empty: {path}")
    try:
        return Config.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(str(exc)) from exc


def resolve_bundle_thresholds(bundle: Bundle, defaults: Defaults) -> tuple[float, float]:
    include = bundle.include_if_peak_elevation_deg
    if include is None:
        include = defaults.include_if_peak_elevation_deg
    label = bundle.label_overhead_if_peak_elevation_deg
    if label is None:
        label = defaults.label_overhead_if_peak_elevation_deg
    if label < include:
        raise ConfigError(
            "Bundle "
            f"{bundle.slug} has label_overhead_if_peak_elevation_deg < "
            "include_if_peak_elevation_deg"
        )
    return include, label


def resolve_repo_url(config: Config) -> str:
    """Resolve the repo URL, using GITHUB_REPOSITORY env var if config has placeholder."""
    if config.repo_url and config.repo_url != DEFAULT_REPO_URL_PLACEHOLDER:
        return config.repo_url

    github_repo = os.environ.get("GITHUB_REPOSITORY")
    if github_repo:
        return f"https://github.com/{github_repo}"

    return config.repo_url


def resolve_featured_locations(config: Config) -> list[Location]:
    if config.featured_locations:
        return config.featured_locations
    if config.locations:
        return config.locations
    return []


def resolve_featured_bundles(config: Config) -> list[Bundle]:
    if not config.featured_bundles:
        return config.bundles
    bundle_map = {bundle.slug: bundle for bundle in config.bundles}
    return [bundle_map[slug] for slug in config.featured_bundles]


def load_requests(requests_dir: Path, config: Config) -> list[RequestedLocation]:
    """Load all request files from the requests directory.

    Args:
        requests_dir: Path to the config/requests/ directory.
        config: The main config, used to validate bundle_slug.

    Returns:
        List of RequestedLocation instances.

    Raises:
        ConfigError: If a request file is invalid or references unknown bundle.
    """
    if not requests_dir.exists():
        return []

    bundle_slugs = {b.slug for b in config.bundles}
    requests: list[RequestedLocation] = []

    for path in sorted(requests_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text())
        except Exception as exc:
            raise ConfigError(f"Failed to parse request file {path}: {exc}") from exc

        if data is None:
            continue

        if isinstance(data, dict):
            slug = data.get("slug")
            if not slug:
                lat = data.get("lat")
                lon = data.get("lon")
                if lat is not None and lon is not None:
                    try:
                        data["slug"] = compute_location_slug(
                            float(lat),
                            float(lon),
                            config.request_defaults.slug_precision_decimals,
                        )
                    except (TypeError, ValueError):
                        pass

        try:
            req = RequestedLocation.model_validate(data)
        except ValidationError as exc:
            raise ConfigError(f"Invalid request file {path}: {exc}") from exc

        if req.bundle_slug not in bundle_slugs:
            raise ConfigError(f"Request file {path} references unknown bundle: {req.bundle_slug}")

        if req.slug and "--" in req.slug:
            parts = req.slug.split("--")
            if len(parts) >= 2 and parts[1] != req.bundle_slug:
                raise ConfigError(
                    f"Request file {path} slug bundle does not match bundle_slug: {req.slug}"
                )

        requests.append(req)

    return requests
