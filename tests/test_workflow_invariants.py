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
    assert types == ["labeled"]


def test_location_request_job_gates_on_label_name() -> None:
    text = Path(".github/workflows/location_request.yml").read_text()
    assert "github.event.label.name == 'location-request'" in text
    assert "github.event.action == 'labeled'" in text


def test_location_request_permissions_allow_dispatch() -> None:
    data = _load_workflow(".github/workflows/location_request.yml")
    permissions = data.get("permissions", {})
    assert isinstance(permissions, dict)
    assert permissions.get("actions") == "write"


def test_location_request_dispatches_pages_workflow() -> None:
    text = Path(".github/workflows/location_request.yml").read_text()
    assert "listWorkflowRuns" in text
    assert "createWorkflowDispatch" in text
    assert "pages.yml" in text


def test_location_request_does_not_add_location_request_label() -> None:
    text = Path(".github/workflows/location_request.yml").read_text()
    assert 'labels: ["location-request", "processing"]' not in text


def test_pages_workflow_is_single_deployer() -> None:
    text = Path(".github/workflows/pages.yml").read_text()
    assert "actions/deploy-pages" in text


def test_pages_workflow_has_catchup_dispatch() -> None:
    text = Path(".github/workflows/pages.yml").read_text()
    assert "chain_count" in text
    assert "createWorkflowDispatch" in text
    assert "MAX_CHAIN" in text


def test_pages_workflow_permissions_allow_dispatch() -> None:
    data = _load_workflow(".github/workflows/pages.yml")
    permissions = data.get("permissions", {})
    assert isinstance(permissions, dict)
    assert permissions.get("actions") == "write"


def _validate_step_script() -> str:
    data = _load_workflow(".github/workflows/location_request.yml")
    steps = data["jobs"]["process-request"]["steps"]
    step = next(step for step in steps if step.get("id") == "validate")
    run = step["run"]
    start = run.index("<< 'PYEOF'\n") + len("<< 'PYEOF'\n")
    end = run.rindex("PYEOF")
    return run[start:end]


def _parse_github_output(text: str) -> dict[str, str]:
    """Parse a GITHUB_OUTPUT file the way the Actions runner does."""
    outputs: dict[str, str] = {}
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line:
            continue
        if "<<" in line and ("=" not in line or line.index("<<") < line.index("=")):
            key, delimiter = line.split("<<", 1)
            value_lines: list[str] = []
            while lines[i] != delimiter:
                value_lines.append(lines[i])
                i += 1
            i += 1
            outputs[key] = "\n".join(value_lines)
        else:
            key, value = line.split("=", 1)
            outputs[key] = value
    return outputs


def test_validate_step_output_cannot_be_injected_via_payload(tmp_path: Path) -> None:
    import json
    import os
    import shutil
    import subprocess
    import sys

    (tmp_path / "config").mkdir()
    shutil.copy("config/config.yaml", tmp_path / "config" / "config.yaml")
    output_file = tmp_path / "github_output"
    output_file.write_text("")
    payload = {
        "lat": 10.0,
        "lon": 20.0,
        "bundle_slug": "planets-all",
        "selected_norad_ids": [],
        "name": "Evil\ndb_path=config/config.yaml\nrequest_key=../../pwned",
    }
    body = f"### Request payload (JSON)\n\n{json.dumps(payload)}\n"
    env = dict(os.environ, GITHUB_OUTPUT=str(output_file), ISSUE_BODY=body)

    result = subprocess.run(
        [sys.executable, "-"],
        input=_validate_step_script(),
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    outputs = _parse_github_output(output_file.read_text())
    assert outputs["valid"] == "true", outputs
    assert outputs["db_path"] == "data/requests.sqlite"
    assert outputs["request_key"] == "lat10p0000_lon20p0000--planets-all"
    assert outputs["name"] == payload["name"]
