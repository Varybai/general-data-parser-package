#!/usr/bin/env python3
"""Verify portable skill resources, local links, and JSON template syntax."""

import json
from pathlib import Path
import re


def check(root):
    root = root.resolve()
    entry = (root / "SKILL.md").read_text(encoding="utf-8")
    assert re.match(r"^---\nname: general-data-parser\ndescription: .+\n---\n", entry)
    files = [p for p in root.rglob("*") if p.is_file()]
    links, templates = 0, 0
    for path in root.rglob("*"):
        assert not path.is_symlink(), f"symlink: {path}"
    for path in files:
        assert path.suffix in {".md", ".py", ".yaml"}, f"unexpected payload: {path}"
        body = path.read_text(encoding="utf-8")
        assert not re.search(r"/Users/[^/\s]+/|[A-Z]:\\Users\\", body), f"host path: {path}"
        assert "[TODO:" not in body, f"unfinished scaffold: {path}"
        if path.suffix != ".md":
            continue
        marker = None
        for line in body.splitlines():
            fence = re.match(r"^(`{3,}|~{3,})(.*)$", line)
            if fence:
                if marker is None:
                    marker = fence[1]
                elif fence[1][0] == marker[0] and len(fence[1]) >= len(marker) and not fence[2].strip():
                    marker = None
        assert marker is None, f"unclosed code fence: {path}"
        # Template link placeholders are intentional and not static resource references.
        for target in re.findall(r"\]\(([^)]+)\)", body):
            if "://" in target or target.startswith("#") or "{" in target:
                continue
            resolved = (path.parent / target.split("#", 1)[0]).resolve()
            assert resolved.is_relative_to(root) and resolved.is_file(), f"broken resource: {path}: {target}"
            links += 1
        for raw in re.findall(r"^```json\n(.*?)\n```", body, re.M | re.S):
            assert isinstance(json.loads(raw), dict)
            templates += 1
    assert templates == 5, f"expected five envelope templates, found {templates}"
    result = {"status": "pass", "payload_files": len(files), "resource_links": links, "json_templates": templates}
    print(json.dumps(result, indent=2))
    return result


def check_pi_manifest(package):
    data = json.loads((package / "package.json").read_text(encoding="utf-8"))
    assert data["name"] == "general-data-parser-package"
    assert data["pi"] == {"skills": ["./skills"]}
    assert "pi-package" in data["keywords"]
    assert "skills/" in data["files"]
    assert not data.get("dependencies"), "portable skill must not require root npm dependencies"
    lifecycle = {"preinstall", "install", "postinstall", "prepare"}
    assert not lifecycle.intersection(data.get("scripts", {})), "unexpected install lifecycle script"
    return {"pi_manifest": "pass", "shared_skill_root": "skills/"}


if __name__ == "__main__":
    package = Path(__file__).resolve().parents[1]
    check(package / "skills" / "general-data-parser")
    print(json.dumps(check_pi_manifest(package)))
