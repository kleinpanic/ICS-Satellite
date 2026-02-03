from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


def _bundle_slugs() -> list[str]:
    config = yaml.safe_load(Path("config/config.yaml").read_text())
    bundles = config.get("bundles", [])
    return [bundle["slug"] for bundle in bundles if "slug" in bundle]


def _issue_template_options() -> list[str]:
    template = yaml.safe_load(Path(".github/ISSUE_TEMPLATE/location_request.yml").read_text())
    for item in template.get("body", []):
        if item.get("type") != "markdown":
            continue
        value = item.get("attributes", {}).get("value", "")
        if "<!-- BUNDLE_LIST_START -->" not in value:
            continue
        lines = value.splitlines()
        start = lines.index("<!-- BUNDLE_LIST_START -->")
        end = lines.index("<!-- BUNDLE_LIST_END -->")
        slugs = []
        for line in lines[start + 1 : end]:
            stripped = line.strip()
            if stripped.startswith("- "):
                slugs.append(stripped[2:].strip())
        return slugs
    return []


def test_issue_template_bundle_options_match_config() -> None:
    assert _issue_template_options() == _bundle_slugs()


def test_issue_template_bundle_slug_input_present() -> None:
    template = yaml.safe_load(Path(".github/ISSUE_TEMPLATE/location_request.yml").read_text())
    input_ids = {item.get("id") for item in template.get("body", []) if item.get("type") == "input"}
    dropdown_ids = {
        item.get("id") for item in template.get("body", []) if item.get("type") == "dropdown"
    }
    assert "bundle_slug" in input_ids
    assert "bundle" not in dropdown_ids


def test_sync_issue_template_check() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/sync_issue_template.py", "--check"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
