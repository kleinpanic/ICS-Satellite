"""Tests for TLE fetching and selection behavior."""

from pathlib import Path
from unittest.mock import patch

from satpass.tle import fetch_tles

GROUP_TLE = """ISS (ZARYA)
1 25544U 98067A   24120.51782528  .00021784  00000-0  38309-3 0  9991
2 25544  51.6411 159.9641 0004568  37.1152  67.4875 15.50283102447526
NOAA 15
1 25338U 98030A   24120.54158083  .00000072  00000-0  69392-4 0  9991
2 25338  98.7123  95.5367 0011180  91.8437 268.4142 14.25955790227306
"""

CATNR_TLE = """ISS (ZARYA)
1 25544U 98067A   24120.51782528  .00021784  00000-0  38309-3 0  9991
2 25544  51.6411 159.9641 0004568  37.1152  67.4875 15.50283102447526
"""


@patch("satpass.tle._fetch_with_cache")
def test_fetch_tles_group_only(mock_fetch: patch) -> None:
    mock_fetch.return_value = GROUP_TLE
    tles = fetch_tles(cache_dir=Path("cache"), ttl_hours=1, groups=["stations"], norad_ids=[])
    assert len(tles) == 2
    names = {tle.name for tle in tles}
    assert "ISS (ZARYA)" in names
    assert "NOAA 15" in names


@patch("satpass.tle._fetch_with_cache")
def test_fetch_tles_ids_only(mock_fetch: patch) -> None:
    mock_fetch.return_value = CATNR_TLE
    tles = fetch_tles(cache_dir=Path("cache"), ttl_hours=1, groups=[], norad_ids=[25544])
    assert len(tles) == 1
    assert tles[0].norad_id == 25544
    assert tles[0].name == "ISS (ZARYA)"


@patch("satpass.tle._fetch_with_cache")
def test_fetch_tles_group_and_ids_intersection(mock_fetch: patch) -> None:
    mock_fetch.return_value = GROUP_TLE
    tles = fetch_tles(cache_dir=Path("cache"), ttl_hours=1, groups=["stations"], norad_ids=[25544])
    assert len(tles) == 1
    assert tles[0].norad_id == 25544
    assert tles[0].name == "ISS (ZARYA)"
