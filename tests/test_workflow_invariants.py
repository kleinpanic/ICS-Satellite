from __future__ import annotations

from pathlib import Path

import yaml


def _load_workflow(path: str) -> dict:
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, dict):
        raise AssertionError(f"Workflow {path} did not parse to a dict.")
    return data


def _workflow_on(data: dict) -> dict:
    on_section = data.get("on")
    if on_section is None:
        on_section = data.get(True)
    return on_section if isinstance(on_section, dict) else {}


def test_location_request_has_no_pages_deploy() -> None:
    text = Path(".github/workflows/location_request.yml").read_text()
    assert "actions/deploy-pages" not in text
    assert "actions/upload-pages-artifact" not in text
    assert "environment:\n      name: github-pages" not in text


def test_location_request_not_triggered_on_edited() -> None:
    data = _load_workflow(".github/workflows/location_request.yml")
    on_section = _workflow_on(data)
    issues = on_section.get("issues", {})
    types = issues.get("types", []) if isinstance(issues, dict) else []
    assert "edited" not in types


def test_location_request_permissions_allow_dispatch() -> None:
    data = _load_workflow(".github/workflows/location_request.yml")
    permissions = data.get("permissions", {})
    assert isinstance(permissions, dict)
    assert permissions.get("actions") == "write"


def test_location_request_dispatches_pages_workflow() -> None:
    text = Path(".github/workflows/location_request.yml").read_text()
    assert "createWorkflowDispatch" in text
    assert "pages.yml" in text


def test_pages_workflow_is_single_deployer() -> None:
    text = Path(".github/workflows/pages.yml").read_text()
    assert "actions/deploy-pages" in text
