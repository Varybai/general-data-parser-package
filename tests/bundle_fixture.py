"""Tiny local conversion fixtures; simulated review records are test-only."""

import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import platform
import sys

sys.dont_write_bytecode = True
PACKAGE = Path(__file__).resolve().parents[1]
SKILL = PACKAGE / "skills" / "general-data-parser"
spec = importlib.util.spec_from_file_location("bundle_verifier", SKILL / "scripts" / "verify_bundle.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def dump(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def load(root, name):
    return json.loads((root / name).read_text(encoding="utf-8"))


def refresh(root, rebind=True):
    profile = load(root, "profile.json")
    role_paths = {value: key for key, value in profile["roles"].items()}
    role_paths["profile.json"] = "profile"

    def inventory():
        entries = []
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.name in {"manifest.json", "acceptance.json"}:
                continue
            name = path.relative_to(root).as_posix()
            role = role_paths.get(name)
            if role is None:
                role = "source" if name.startswith("source/") else "receipt"
            raw = path.read_bytes()
            entries.append({"path": name, "role": role, "sha256": sha(raw), "size_bytes": len(raw)})
        return entries

    files = inventory()
    source_rows = [{key: item[key] for key in ("path", "role", "sha256")}
                   for item in files if item["role"] in {"source", "dependency"}]
    source_sha = sha(json.dumps(source_rows, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":"), allow_nan=False).encode())
    report = load(root, "acceptance.json")
    if rebind:
        metadata_paths = [profile["roles"][role] for role in ("facts", "observations")
                          if role in profile["roles"]] + ["acceptance.json"]
        for name in metadata_paths:
            data = load(root, name)
            data["source_manifest_sha256"] = source_sha
            data["profile_sha256"] = sha((root / "profile.json").read_bytes())
            dump(root, name, data)
        report = load(root, "acceptance.json")
    manifest = {"schema_version": "general-parser.manifest.v1", "object_id": report["object_id"],
                "version": report["version"], "files": inventory()}
    dump(root, "manifest.json", manifest)
    report["manifest_sha256"] = sha((root / "manifest.json").read_bytes())
    dump(root, "acceptance.json", report)


def make_bundle(root, kind="csv", reviewed=False):
    root.mkdir(parents=True, exist_ok=True)
    raw_inputs = {
        "csv": 'sku,quantity,note\nA,2,"comma, note"\nB,0,\nC,3,final\n',
        "json": '{"id":9007199254740993,"items":[1,null,0],"empty":[],"label":"零件"}\n',
        "md": '# 样本\n\n数量：3。\n禁止把未知值填为 0。\n',
    }
    raw = raw_inputs[kind]
    source_name = "source/input." + kind
    (root / "source").mkdir(exist_ok=True)
    (root / source_name).write_bytes(raw.encode("utf-8"))
    if kind == "csv":
        parsed = list(csv.DictReader(io.StringIO(raw)))
        expected = [{"sku": "A", "quantity": "2", "note": "comma, note"},
                    {"sku": "B", "quantity": "0", "note": ""},
                    {"sku": "C", "quantity": "3", "note": "final"}]
        assert parsed == expected and sum(int(row["quantity"]) for row in parsed) == 5
        count, tool, location = len(parsed), "Python csv.DictReader", {"rows": [2, 4], "row_base": 1}
    elif kind == "json":
        parsed = verifier.strict_json(raw)
        expected = {"id": 9007199254740993, "items": [1, None, 0], "empty": [], "label": "零件"}
        assert parsed == expected and type(parsed["id"]) is int
        count, tool, location = len(parsed), "Python strict JSON", {"json_pointer": ""}
    else:
        parsed = (root / source_name).read_text(encoding="utf-8").splitlines()
        expected = ["# 样本", "", "数量：3。", "禁止把未知值填为 0。"]
        assert parsed == expected
        count, tool, location = len(parsed), "Python UTF-8 line reader", {"lines": [1, 4], "line_base": 1}
    required = ["content.fidelity", "content.coverage", "document.consistency", "format." + kind]
    profile = {
        "schema_version": "general-parser.profile.v1", "id": "fixture." + kind + ".v1",
        "format": kind, "output_language": "zh",
        "adapter": {"tool": tool, "version": platform.python_version(), "options": {},
                    "supported_scope": ["synthetic small fixture only"]},
        "roles": {"facts": "facts.json", "observations": "observations.json", "asset": "asset.md",
                  "abstract": ".abstract.md", "overview": ".overview.md"},
        "observation_policy": "required" if reviewed else "not_applicable",
        "summary_owner": "local",
        "overview_relation": "identical", "required_checks": required,
    }
    if reviewed:
        required.append("observation.consistency")
    dump(root, "profile.json", profile)
    identity = {"object_id": "sample-" + kind, "version": "v1", "profile_sha256": "", "source_manifest_sha256": ""}
    facts = {
        "schema_version": "general-parser.facts.v1", **identity,
        "extraction": {"status": "succeeded", "tool": tool, "tool_version": platform.python_version(),
                       "receipt": "receipts/parse.json", "losses": []},
        "claims": [{"id": "parsed", "kind": "extracted", "status": "known", "value": parsed, "unit": None,
                    "basis": [{"path": source_name, "locator": location, "method": tool}], "reason": None},
                   {"id": "count", "kind": "computed", "status": "known", "value": count, "unit": "entries",
                    "basis": [{"path": "receipts/parse.json", "locator": {"field": "count"},
                               "method": "count parsed entries; compare independent fixture expectation"}], "reason": None}],
        "diagnostics": [], "limitations": ["Validation applies only to this synthetic fixture."],
    }
    dump(root, "facts.json", facts)
    dump(root, "receipts/parse.json", {"tool": tool, "source": source_name, "input_sha256": sha(raw.encode()),
                                       "count": count, "output": parsed, "status": "succeeded"})
    observation = {"schema_version": "general-parser.observations.v1", **identity,
                   "review_status": "skipped", "observer": None, "observed_at": None, "items": [],
                   "hypotheses": [], "reason": "Text/structured fixture is checked directly against source."}
    if reviewed:
        # This branch exercises schema/gates, not a real image or model call.
        dump(root, "receipts/observation.json", {"test_only": True, "execution": "simulated reviewer"})
        observation.update({"review_status": "reviewed", "observer": {
            "kind": "model", "id": "simulated-test-observer", "receipt": "receipts/observation.json"},
            "observed_at": "2026-10-09T00:00:00+00:00", "reason": None,
            "items": [{"id": "observation-1", "kind": "semantic", "text": "Synthetic schema fixture.",
                       "basis": [{"path": source_name, "locator": location, "method": "simulated test"}],
                       "limitations": ["Not real perception evidence."]}]})
    dump(root, "observations.json", observation)
    body = f"# sample-{kind}@v1\n\n条目数：{count}。\n\n[源文件]({source_name}) · [完整事实](facts.json)\n\n"
    body += "## 源数据\n\n```json\n" + json.dumps(parsed, ensure_ascii=False, indent=2) + "\n```\n\n"
    body += "## 范围\n\n本次自建样本全部读取；不推断源未提供的现实事实。\n"
    for name in ("asset.md", ".overview.md"):
        (root / name).write_text(body, encoding="utf-8")
    (root / ".abstract.md").write_text(f"sample-{kind}：{count} 条目；自建样本全量读取，结论仅覆盖该样本。\n", encoding="utf-8")
    recovered = json.loads(body.split("```json\n", 1)[1].split("\n```", 1)[0])
    assert recovered == expected
    assert (root / "asset.md").read_bytes() == (root / ".overview.md").read_bytes()
    dump(root, "receipts/content-check.json", {
        "executed": True, "method": "Compare parsed values and document JSON against independent fixture constants",
        "expected": expected, "actual": parsed, "document_values": recovered, "count": count,
        "coverage": "all fixture bytes/records read", "result": "pass",
        "observation_note": "No real model call; reviewed variant is a contract-test fixture only.",
    })
    report = {"schema_version": "general-parser.acceptance.v1", **identity, "manifest_sha256": "",
              "state": "local_ready", "limitations": [], "checks": [
                  {"id": cid, "executed": True, "result": "pass",
                   "method": "Independent fixture constants and document roundtrip comparison",
                   "evidence": ["receipts/content-check.json"], "reason": None} for cid in required]}
    dump(root, "acceptance.json", report)
    refresh(root)
    return root
