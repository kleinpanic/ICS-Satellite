from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from skyfield.api import Loader

# Persistent cache shared across test runs (not per-tmp_path).
# CI caches this directory to avoid re-downloading every run.
_EPHEMERIS_CACHE = Path(".cache/ephemeris")
_EPHEMERIS_FILE = "de421.bsp"


def _ensure_ephemeris_cached() -> Path:
    """Ensure de421.bsp exists in the persistent cache, downloading if needed."""
    _EPHEMERIS_CACHE.mkdir(parents=True, exist_ok=True)
    cached = _EPHEMERIS_CACHE / _EPHEMERIS_FILE
    if not cached.exists():
        loader = Loader(str(_EPHEMERIS_CACHE))
        loader(_EPHEMERIS_FILE)
    return cached


@pytest.fixture
def ephemeris_state_dir(tmp_path: Path) -> Path:
    """Return a tmp state_dir with ephemeris ready for load_ephemeris().

    The ephemeris is kept in a persistent cache (.cache/ephemeris/) and
    copied into the test's tmp directory so each test gets an isolated
    state_dir while avoiding repeated downloads.
    """
    cached = _ensure_ephemeris_cached()
    dest_dir = tmp_path / "ephemeris"
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(cached, dest_dir / _EPHEMERIS_FILE)
    return tmp_path
