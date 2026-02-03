#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml


def load_bundle_slugs(config_path: Path) -> list[str]:
    data = yaml.safe_load(config_path.read_text())
    bundles = data.get("bundles", []) if isinstance(data, dict) else []
    slugs = []
    for bundle in bundles:
        slug = bundle.get("slug") if isinstance(bundle, dict) else None
        if slug:
            slugs.append(slug)
    return slugs


def update_template(text: str, bundle_slugs: list[str]) -> str:
    lines = text.splitlines()
    start_marker = "<!-- BUNDLE_LIST_START -->"
    end_marker = "<!-- BUNDLE_LIST_END -->"
    start_index = None
    end_index = None

    for idx, line in enumerate(lines):
        if start_marker in line:
            start_index = idx
        if end_marker in line:
            end_index = idx

    if start_index is None or end_index is None or end_index <= start_index:
        raise ValueError("Could not find bundle list markers in issue template")

    base_indent = re.match(r"^(\s*)", lines[start_index]).group(1)
    new_lines = [f"{base_indent}- {slug}" for slug in bundle_slugs]
    updated = lines[: start_index + 1] + new_lines + lines[end_index:]
    suffix = "\n" if text.endswith("\n") else ""
    return "\n".join(updated) + suffix


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Issue template bundle options")
    parser.add_argument("--config", default="config/config.yaml")
    parser.add_argument("--template", default=".github/ISSUE_TEMPLATE/location_request.yml")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config)
    template_path = Path(args.template)

    bundle_slugs = load_bundle_slugs(config_path)
    if not bundle_slugs:
        raise SystemExit("No bundle slugs found in config")

    original = template_path.read_text()
    updated = update_template(original, bundle_slugs)

    if args.check:
        if updated != original:
            sys.stderr.write("Issue template bundle options are out of sync.\n")
            return 1
        return 0

    if updated != original:
        template_path.write_text(updated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
