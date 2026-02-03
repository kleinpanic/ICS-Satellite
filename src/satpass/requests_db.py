from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from .config import Config, RequestedLocation
from .slug import compute_location_slug, compute_request_feed_slug


@dataclass(frozen=True)
class RequestRecord:
    request_key: str
    location_slug: str
    location_key: str
    bundle_slug: str
    lat: float
    lon: float
    elevation_m: float | None
    name: str | None
    selected_norad_ids: list[int]
    requested_by: str | None
    requested_at: str | None
    first_seen: str
    last_seen: str


class RequestDBError(RuntimeError):
    pass


def init_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS requests (
            request_key TEXT PRIMARY KEY,
            location_slug TEXT NOT NULL,
            location_key TEXT NOT NULL,
            bundle_slug TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            elevation_m REAL,
            name TEXT,
            selected_norad_ids TEXT,
            requested_by TEXT,
            requested_at TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL
        )
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(requests)")}
    if "location_key" not in columns:
        conn.execute("ALTER TABLE requests ADD COLUMN location_key TEXT")
    conn.commit()
    return conn


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_norad_ids(norad_ids: Iterable[int] | None) -> list[int]:
    if not norad_ids:
        return []
    return sorted({int(norad_id) for norad_id in norad_ids})


def selection_payload(norad_ids: Iterable[int] | None) -> str:
    return json.dumps(normalize_norad_ids(norad_ids))


def location_key_for(lat: float, lon: float, precision: int) -> str:
    return compute_location_slug(lat, lon, precision)


def canonicalize_selection(
    selected_norad_ids: Iterable[int] | None,
    available_norad_ids: Iterable[int] | None,
) -> list[int]:
    selected = normalize_norad_ids(selected_norad_ids)
    available = normalize_norad_ids(available_norad_ids)
    if selected and available:
        available_set = set(available)
        selected = [norad_id for norad_id in selected if norad_id in available_set]
    if selected and available and set(selected) == set(available):
        return []
    return selected


def default_selection(available_norad_ids: Iterable[int] | None, max_satellites: int) -> list[int]:
    available = normalize_norad_ids(available_norad_ids)
    if not available:
        return []
    return available[:max_satellites]


def request_key_for(
    *, location_slug: str, bundle_slug: str, selected_norad_ids: Iterable[int] | None
) -> str:
    return compute_request_feed_slug(
        location_slug=location_slug,
        bundle_slug=bundle_slug,
        selected_norad_ids=normalize_norad_ids(selected_norad_ids),
    )


def upsert_request(
    conn: sqlite3.Connection,
    request: RequestedLocation,
    *,
    precision: int,
) -> RequestRecord:
    location_slug = request.resolved_location_slug(precision=precision)
    location_key = location_key_for(request.lat, request.lon, precision)
    selected_norad_ids = normalize_norad_ids(request.selected_norad_ids)
    key = request_key_for(
        location_slug=location_slug,
        bundle_slug=request.bundle_slug,
        selected_norad_ids=selected_norad_ids,
    )

    now = _utc_now()
    payload = selection_payload(selected_norad_ids)

    ensure_location_keys(conn, precision)
    existing_signature = get_request_by_signature(
        conn,
        location_key=location_key,
        bundle_slug=request.bundle_slug,
        selected_norad_ids=selected_norad_ids,
    )
    if existing_signature:
        requested_by = existing_signature.requested_by or request.requested_by
        requested_at = existing_signature.requested_at or request.requested_at
        conn.execute(
            """
            UPDATE requests
            SET last_seen = ?, name = COALESCE(name, ?), requested_by = COALESCE(requested_by, ?),
                requested_at = COALESCE(requested_at, ?), location_key = COALESCE(location_key, ?)
            WHERE request_key = ?
            """,
            (
                now,
                request.name,
                requested_by,
                requested_at,
                location_key,
                existing_signature.request_key,
            ),
        )
        conn.commit()
        return RequestRecord(
            request_key=existing_signature.request_key,
            location_slug=existing_signature.location_slug,
            location_key=existing_signature.location_key or location_key,
            bundle_slug=existing_signature.bundle_slug,
            lat=existing_signature.lat,
            lon=existing_signature.lon,
            elevation_m=existing_signature.elevation_m,
            name=existing_signature.name or request.name,
            selected_norad_ids=existing_signature.selected_norad_ids,
            requested_by=requested_by,
            requested_at=requested_at,
            first_seen=existing_signature.first_seen,
            last_seen=now,
        )

    existing = conn.execute(
        """
        SELECT request_key, first_seen, requested_by, requested_at
        FROM requests
        WHERE request_key = ?
        """,
        (key,),
    ).fetchone()

    if existing:
        first_seen = existing[1]
        requested_by = existing[2] or request.requested_by
        requested_at = existing[3] or request.requested_at
        conn.execute(
            """
            UPDATE requests
            SET last_seen = ?, name = COALESCE(name, ?), requested_by = COALESCE(requested_by, ?),
                requested_at = COALESCE(requested_at, ?), location_key = COALESCE(location_key, ?)
            WHERE request_key = ?
            """,
            (now, request.name, requested_by, requested_at, location_key, key),
        )
    else:
        first_seen = now
        requested_by = request.requested_by
        requested_at = request.requested_at
        conn.execute(
            """
            INSERT INTO requests (
                request_key, location_slug, location_key, bundle_slug, lat, lon, elevation_m, name,
                selected_norad_ids, requested_by, requested_at, first_seen, last_seen
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                key,
                location_slug,
                location_key,
                request.bundle_slug,
                request.lat,
                request.lon,
                request.elevation_m,
                request.name,
                payload,
                requested_by,
                requested_at,
                first_seen,
                now,
            ),
        )

    conn.commit()

    return RequestRecord(
        request_key=key,
        location_slug=location_slug,
        location_key=location_key,
        bundle_slug=request.bundle_slug,
        lat=request.lat,
        lon=request.lon,
        elevation_m=request.elevation_m,
        name=request.name,
        selected_norad_ids=selected_norad_ids,
        requested_by=requested_by,
        requested_at=requested_at,
        first_seen=first_seen,
        last_seen=now,
    )


def list_requests(conn: sqlite3.Connection) -> list[RequestRecord]:
    rows = conn.execute(
        """
        SELECT request_key, location_slug, location_key, bundle_slug, lat, lon, elevation_m, name,
               selected_norad_ids, requested_by, requested_at, first_seen, last_seen
        FROM requests
        ORDER BY location_slug, bundle_slug, request_key
        """
    ).fetchall()

    records: list[RequestRecord] = []
    for row in rows:
        selected_norad_ids = json.loads(row[8]) if row[8] else []
        records.append(
            RequestRecord(
                request_key=row[0],
                location_slug=row[1],
                location_key=row[2] or "",
                bundle_slug=row[3],
                lat=row[4],
                lon=row[5],
                elevation_m=row[6],
                name=row[7],
                selected_norad_ids=selected_norad_ids,
                requested_by=row[9],
                requested_at=row[10],
                first_seen=row[11],
                last_seen=row[12],
            )
        )
    return records


def get_request_by_key(conn: sqlite3.Connection, request_key: str) -> RequestRecord | None:
    row = conn.execute(
        """
        SELECT request_key, location_slug, location_key, bundle_slug, lat, lon, elevation_m, name,
               selected_norad_ids, requested_by, requested_at, first_seen, last_seen
        FROM requests
        WHERE request_key = ?
        """,
        (request_key,),
    ).fetchone()
    if row is None:
        return None
    selected_norad_ids = json.loads(row[8]) if row[8] else []
    return RequestRecord(
        request_key=row[0],
        location_slug=row[1],
        location_key=row[2] or "",
        bundle_slug=row[3],
        lat=row[4],
        lon=row[5],
        elevation_m=row[6],
        name=row[7],
        selected_norad_ids=selected_norad_ids,
        requested_by=row[9],
        requested_at=row[10],
        first_seen=row[11],
        last_seen=row[12],
    )


def get_request_by_signature(
    conn: sqlite3.Connection,
    *,
    location_key: str,
    bundle_slug: str,
    selected_norad_ids: Iterable[int] | None,
) -> RequestRecord | None:
    payload = selection_payload(selected_norad_ids)
    row = conn.execute(
        """
        SELECT request_key, location_slug, location_key, bundle_slug, lat, lon, elevation_m, name,
               selected_norad_ids, requested_by, requested_at, first_seen, last_seen
        FROM requests
        WHERE location_key = ? AND bundle_slug = ? AND selected_norad_ids = ?
        """,
        (location_key, bundle_slug, payload),
    ).fetchone()
    if row is None:
        return None
    selected = json.loads(row[8]) if row[8] else []
    return RequestRecord(
        request_key=row[0],
        location_slug=row[1],
        location_key=row[2] or "",
        bundle_slug=row[3],
        lat=row[4],
        lon=row[5],
        elevation_m=row[6],
        name=row[7],
        selected_norad_ids=selected,
        requested_by=row[9],
        requested_at=row[10],
        first_seen=row[11],
        last_seen=row[12],
    )


def ensure_location_keys(conn: sqlite3.Connection, precision: int) -> int:
    rows = conn.execute(
        """
        SELECT request_key, lat, lon
        FROM requests
        WHERE location_key IS NULL OR location_key = ''
        """
    ).fetchall()
    if not rows:
        return 0
    for request_key, lat, lon in rows:
        loc_key = location_key_for(float(lat), float(lon), precision)
        conn.execute(
            "UPDATE requests SET location_key = ? WHERE request_key = ?",
            (loc_key, request_key),
        )
    conn.commit()
    return len(rows)


def dedupe_requests_by_signature(conn: sqlite3.Connection, precision: int) -> int:
    ensure_location_keys(conn, precision)
    records = sorted(list_requests(conn), key=lambda record: record.first_seen)
    seen: dict[tuple[str, str, str], RequestRecord] = {}
    removed = 0
    for record in records:
        signature = (
            record.location_key,
            record.bundle_slug,
            selection_payload(record.selected_norad_ids),
        )
        existing = seen.get(signature)
        if not existing:
            seen[signature] = record
            continue
        merged_first = min(existing.first_seen, record.first_seen)
        merged_last = max(existing.last_seen, record.last_seen)
        merged_name = existing.name or record.name
        merged_requested_by = existing.requested_by or record.requested_by
        merged_requested_at = existing.requested_at or record.requested_at
        conn.execute(
            """
            UPDATE requests
            SET name = ?, requested_by = ?, requested_at = ?, first_seen = ?, last_seen = ?
            WHERE request_key = ?
            """,
            (
                merged_name,
                merged_requested_by,
                merged_requested_at,
                merged_first,
                merged_last,
                existing.request_key,
            ),
        )
        conn.execute("DELETE FROM requests WHERE request_key = ?", (record.request_key,))
        removed += 1
    if removed:
        conn.commit()
    return removed


def load_requests_from_db(conn: sqlite3.Connection) -> list[RequestedLocation]:
    requests: list[RequestedLocation] = []
    for record in list_requests(conn):
        requests.append(
            RequestedLocation(
                slug=record.location_slug,
                name=record.name,
                lat=record.lat,
                lon=record.lon,
                elevation_m=record.elevation_m,
                bundle_slug=record.bundle_slug,
                selected_norad_ids=record.selected_norad_ids,
                requested_by=record.requested_by,
                requested_at=record.requested_at,
            )
        )
    return requests


def canonicalize_requests(
    conn: sqlite3.Connection,
    bundle_available_ids: Mapping[str, Iterable[int]],
    max_satellites_per_request: int,
) -> int:
    updated = 0
    for record in list_requests(conn):
        available = bundle_available_ids.get(record.bundle_slug, [])
        selected = normalize_norad_ids(record.selected_norad_ids)
        if not selected:
            selected = default_selection(available, max_satellites_per_request)
        if selected and len(selected) > max_satellites_per_request:
            selected = selected[:max_satellites_per_request]
        canonical_selected = canonicalize_selection(selected, available)
        if canonical_selected == record.selected_norad_ids:
            continue
        new_key = request_key_for(
            location_slug=record.location_slug,
            bundle_slug=record.bundle_slug,
            selected_norad_ids=canonical_selected,
        )
        if new_key == record.request_key:
            continue
        payload = json.dumps(canonical_selected)
        existing = get_request_by_key(conn, new_key)
        if existing:
            merged_first = min(existing.first_seen, record.first_seen)
            merged_last = max(existing.last_seen, record.last_seen)
            merged_name = existing.name or record.name
            merged_requested_by = existing.requested_by or record.requested_by
            merged_requested_at = existing.requested_at or record.requested_at
            conn.execute(
                """
                UPDATE requests
                SET name = ?, requested_by = ?, requested_at = ?, first_seen = ?, last_seen = ?
                WHERE request_key = ?
                """,
                (
                    merged_name,
                    merged_requested_by,
                    merged_requested_at,
                    merged_first,
                    merged_last,
                    new_key,
                ),
            )
            conn.execute(
                "DELETE FROM requests WHERE request_key = ?",
                (record.request_key,),
            )
        else:
            conn.execute(
                """
                UPDATE requests
                SET request_key = ?, selected_norad_ids = ?
                WHERE request_key = ?
                """,
                (new_key, payload, record.request_key),
            )
        updated += 1
    if updated:
        conn.commit()
    return updated


def migrate_yaml_requests(
    *,
    config: Config,
    conn: sqlite3.Connection,
    requests_dir: Path,
) -> list[RequestRecord]:
    from .config import load_requests

    if not requests_dir.exists():
        return []
    yaml_paths = sorted(requests_dir.glob("*.yaml"))
    if not yaml_paths:
        return []

    records: list[RequestRecord] = []
    precision = config.request_defaults.slug_precision_decimals
    for req in load_requests(requests_dir, config):
        records.append(upsert_request(conn, req, precision=precision))
    return records


def write_request_yaml(requests_dir: Path, request: RequestRecord) -> Path:
    import yaml

    requests_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "slug": request.location_slug,
        "name": request.name,
        "lat": request.lat,
        "lon": request.lon,
        "elevation_m": request.elevation_m,
        "bundle_slug": request.bundle_slug,
        "selected_norad_ids": request.selected_norad_ids or None,
        "requested_by": request.requested_by,
        "requested_at": request.requested_at,
        "first_seen": request.first_seen,
        "last_seen": request.last_seen,
    }
    path = requests_dir / f"{request.request_key}.yaml"
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def ensure_db_loaded(
    *,
    config: Config,
    db_path: Path,
    requests_dir: Path,
) -> list[RequestedLocation]:
    conn = init_db(db_path)
    try:
        migrate_yaml_requests(config=config, conn=conn, requests_dir=requests_dir)
        ensure_location_keys(conn, config.request_defaults.slug_precision_decimals)
        return load_requests_from_db(conn)
    finally:
        conn.close()
