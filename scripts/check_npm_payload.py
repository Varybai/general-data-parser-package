#!/usr/bin/env python3
"""Check that npm ships the shared skill and excludes development artifacts."""

import json
from pathlib import Path
import sys


def check(report_path):
    root = Path(__file__).resolve().parents[1]
    reports = json.loads(Path(report_path).read_text(encoding="utf-8"))
    # npm <=11 emits an array; npm 12 emits a map keyed by package name.
    if isinstance(reports, dict):
        reports = [reports] if "files" in reports else list(reports.values())
    assert len(reports) == 1, "expected one npm package"
    report = reports[0]
    assert report["name"] == "general-data-parser-package"
    expected = {"package.json", "README.md"} | {
        path.relative_to(root).as_posix()
        for path in (root / "skills").rglob("*") if path.is_file()
    }
    actual = {item["path"] for item in report["files"]}
    assert actual == expected, f"npm payload differs: {sorted(actual ^ expected)}"
    result = {"status": "pass", "package": report["name"], "version": report["version"], "files": len(actual)}
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    check(sys.argv[1])
