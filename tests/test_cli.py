import subprocess
import sys
from pathlib import Path

import satpass


def test_cli_version_flag() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "satpass", "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert f"satpass {satpass.__version__}" in result.stdout.strip()


def test_cli_reset_requests(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    db_path = tmp_path / "requests.sqlite"
    site_dir = tmp_path / "site"
    feed_dir = site_dir / "feeds"
    feed_dir.mkdir(parents=True)

    config_path.write_text(
        "\n".join(
            [
                "version: 1",
                "repo_url: https://github.com/test/repo",
                "site:",
                "  title: Test",
                "  description: Test",
                "defaults:",
                "  horizon_days: 1",
                "  tle_cache_hours: 12",
                "  refresh_interval_hours: 6",
                "  include_if_peak_elevation_deg: 30",
                "  label_overhead_if_peak_elevation_deg: 80",
                "featured_locations:",
                "  - slug: test",
                "    name: Test",
                "    lat: 0",
                "    lon: 0",
                "bundles:",
                "  - slug: stations",
                "    name: Stations",
                "    celestrak_group: stations",
                f"request_db_path: {db_path}",
            ]
        )
    )

    from satpass.config import RequestedLocation, load_config
    from satpass.requests_db import init_db, upsert_request

    config = load_config(config_path)
    conn = init_db(Path(config.request_db_path))
    try:
        record = upsert_request(
            conn,
            RequestedLocation(lat=10, lon=20, bundle_slug="stations"),
            precision=config.request_defaults.slug_precision_decimals,
        )
    finally:
        conn.close()

    feed_path = feed_dir / f"{record.request_key}.ics"
    feed_path.write_text("dummy")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "satpass",
            "reset-requests",
            "--config",
            str(config_path),
            "--out",
            str(site_dir),
            "--yes",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert not db_path.exists()
    assert not feed_path.exists()
