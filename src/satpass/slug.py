from __future__ import annotations


def _normalize_norad_ids(norad_ids: list[int] | None) -> list[int]:
    if not norad_ids:
        return []
    return sorted({int(norad_id) for norad_id in norad_ids})


def selection_hash(norad_ids: list[int] | None) -> str:
    """Create a deterministic short hash for a set of NORAD IDs."""
    normalized = _normalize_norad_ids(norad_ids)
    payload = ",".join(str(norad_id) for norad_id in normalized)
    hash_val = 2166136261
    for char in payload.encode("utf-8"):
        hash_val ^= char
        hash_val = (hash_val * 16777619) & 0xFFFFFFFF
    return f"{hash_val:08x}"


def format_coordinate(value: float, precision: int) -> str:
    """Format a coordinate value for use in slugs.

    Rounds to N decimal places, replaces decimal point with 'p',
    and prefixes negative values with 'm'.

    Examples:
        40.7128 -> "40p7128"
        -74.0060 -> "m74p0060"
        -0.1234 -> "m0p1234"
    """
    rounded = round(value, precision)
    sign = "m" if rounded < 0 else ""
    abs_val = abs(rounded)

    if precision == 0:
        return f"{sign}{int(abs_val)}"

    formatted = f"{abs_val:.{precision}f}"
    formatted = formatted.replace(".", "p")
    return f"{sign}{formatted}"


def compute_location_slug(
    lat: float,
    lon: float,
    precision: int = 4,
) -> str:
    """Generate a deterministic location slug from lat/lon.

    The slug format is: lat<lat>_lon<lon>
    where lat/lon use 'p' for decimal point and 'm' prefix for negative.

    Args:
        lat: Latitude in decimal degrees (-90 to 90).
        lon: Longitude in decimal degrees (-180 to 180).
        precision: Number of decimal places to round to.

    Returns:
        A filesystem-safe, deterministic slug string.

    Examples:
        (40.7128, -74.0060) -> "lat40p7128_lonm74p0060"
        (47.6062, -122.3321) -> "lat47p6062_lonm122p3321"
    """
    lat_part = format_coordinate(lat, precision)
    lon_part = format_coordinate(lon, precision)
    return f"lat{lat_part}_lon{lon_part}"


def compute_feed_slug(
    lat: float,
    lon: float,
    bundle_slug: str,
    precision: int = 4,
) -> str:
    """Generate a deterministic feed slug from lat/lon/bundle.

    The slug format is: lat<lat>_lon<lon>--<bundle>
    This is the filename (without .ics) for the feed.

    Args:
        lat: Latitude in decimal degrees (-90 to 90).
        lon: Longitude in decimal degrees (-180 to 180).
        bundle_slug: The bundle identifier.
        precision: Number of decimal places to round to.

    Returns:
        A filesystem-safe, deterministic slug string.

    Examples:
        (40.7128, -74.0060, "stations") -> "lat40p7128_lonm74p0060--stations"
        (47.6062, -122.3321, "noaa") -> "lat47p6062_lonm122p3321--noaa"
    """
    location_slug = compute_location_slug(lat, lon, precision)
    return f"{location_slug}--{bundle_slug}"


def compute_request_feed_slug(
    *,
    location_slug: str,
    bundle_slug: str,
    selected_norad_ids: list[int] | None,
) -> str:
    """Generate a feed slug for a requested feed, optionally including a satellite subset."""
    if not selected_norad_ids:
        return f"{location_slug}--{bundle_slug}"
    digest = selection_hash(selected_norad_ids)
    return f"{location_slug}--{bundle_slug}--sel-{digest}"


def parse_location_slug(slug: str) -> tuple[float, float] | None:
    """Parse a location slug back into lat/lon.

    Returns None if the slug doesn't match the expected format.
    """
    try:
        if not slug.startswith("lat"):
            return None
        coord_part = slug[3:]  # Remove 'lat' prefix
        if "_lon" not in coord_part:
            return None
        lat_str, lon_str = coord_part.split("_lon", 1)
        lat = _parse_coord(lat_str)
        lon = _parse_coord(lon_str)
        return lat, lon
    except (ValueError, IndexError):
        return None


def parse_feed_slug(slug: str) -> tuple[float, float, str] | None:
    """Parse a feed slug back into lat/lon/bundle.

    Returns None if the slug doesn't match the expected format.
    """
    try:
        if "--" not in slug:
            return None
        coord_part, bundle_slug = slug.rsplit("--", 1)
        result = parse_location_slug(coord_part)
        if result is None:
            return None
        lat, lon = result
        return lat, lon, bundle_slug
    except (ValueError, IndexError):
        return None


def _parse_coord(s: str) -> float:
    """Parse a coordinate string back to float."""
    sign = -1 if s.startswith("m") else 1
    if s.startswith("m"):
        s = s[1:]
    s = s.replace("p", ".")
    return sign * float(s)
