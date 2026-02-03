from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import requests

CELESTRAK_BASE = "https://celestrak.org/NORAD/elements/gp.php"


@dataclass(frozen=True)
class TLE:
    name: str
    line1: str
    line2: str
    norad_id: int


class TLEError(RuntimeError):
    pass


def _parse_norad_id(line1: str) -> int:
    return int(line1[2:7])


def _parse_tle_block(lines: list[str]) -> list[TLE]:
    tles: list[TLE] = []
    pending_name: str | None = None
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        if line.startswith("1 ") and i + 1 < len(lines):
            line1 = line
            line2 = lines[i + 1].strip()
            if not line2.startswith("2 "):
                i += 1
                continue
            norad_id = _parse_norad_id(line1)
            name = pending_name or f"NORAD {norad_id}"
            pending_name = None
            tles.append(TLE(name=name, line1=line1, line2=line2, norad_id=norad_id))
            i += 2
            continue

        if line.startswith("2 "):
            i += 1
            continue

        pending_name = line
        i += 1
    return tles


def filter_tles_by_ids(tles: Iterable[TLE], norad_ids: Iterable[int]) -> list[TLE]:
    wanted = {int(norad_id) for norad_id in norad_ids}
    return [tle for tle in tles if tle.norad_id in wanted]


def _fetch_with_cache(url: str, path: Path, ttl_hours: int) -> str:
    if path.exists():
        age = datetime.now(timezone.utc) - datetime.fromtimestamp(
            path.stat().st_mtime, timezone.utc
        )
        if age < timedelta(hours=ttl_hours):
            return path.read_text()
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(response.text)
    return response.text


def _bundle_cache_path(cache_dir: Path, suffix: str) -> Path:
    safe = suffix.replace("/", "_").replace(":", "_")
    return cache_dir / f"{safe}.tle"


def fetch_tles(
    *,
    cache_dir: Path,
    ttl_hours: int,
    groups: Iterable[str],
    norad_ids: Iterable[int],
) -> list[TLE]:
    tles: dict[int, TLE] = {}
    groups = list(groups)
    norad_ids_list = list(norad_ids)

    if groups:
        for group in groups:
            url = f"{CELESTRAK_BASE}?GROUP={group}&FORMAT=TLE"
            cache_path = _bundle_cache_path(cache_dir, f"group-{group}")
            text = _fetch_with_cache(url, cache_path, ttl_hours)
            for tle in _parse_tle_block(text.splitlines()):
                tles[tle.norad_id] = tle
        if norad_ids_list:
            filtered = filter_tles_by_ids(tles.values(), norad_ids_list)
            tles = {tle.norad_id: tle for tle in filtered}
    else:
        for norad_id in norad_ids_list:
            url = f"{CELESTRAK_BASE}?CATNR={norad_id}&FORMAT=TLE"
            cache_path = _bundle_cache_path(cache_dir, f"norad-{norad_id}")
            text = _fetch_with_cache(url, cache_path, ttl_hours)
            for tle in _parse_tle_block(text.splitlines()):
                tles[tle.norad_id] = tle

    if not tles:
        raise TLEError("No TLEs fetched. Check bundle configuration.")
    return sorted(tles.values(), key=lambda item: item.norad_id)
