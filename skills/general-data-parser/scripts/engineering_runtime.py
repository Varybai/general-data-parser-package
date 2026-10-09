"""Build and independently replay engineering parsing bundles."""

import json
from pathlib import Path
import platform
import re
import tempfile

import engineering_adapters as adapters
import verify_bundle as contract


TOOL = "general-data-parser.engineering"
DEFAULT_OPTIONS = {
    "encoding": "utf-8-sig", "header": True, "max_bytes": 32 * 1024 * 1024, "max_items": 100000,
    "length_unit": None, "require_unit": False, "time_column": None, "time_unit": None,
    "time_order": "strict", "abs_tolerance": 1e-9, "rel_tolerance": 1e-12,
    "require_observation": False,
}
CODE_FILES = ("engineering_adapters.py", "engineering_runtime.py", "parse_file.py",
              "verify_engineering.py", "verify_bundle.py")


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def write_json(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def implementation_hash():
    root = Path(__file__).resolve().parent
    return contract.digest(contract.canonical({name: contract.digest((root / name).read_bytes()) for name in CODE_FILES}))


def validate_options(options):
    import math
    contract.require(set(options) == set(DEFAULT_OPTIONS), "engineering option set mismatch")
    for name in ("header", "require_unit", "require_observation"):
        contract.require(type(options[name]) is bool, f"invalid {name}")
    for name in ("max_bytes", "max_items"):
        contract.require(type(options[name]) is int and 0 < options[name] <= 1024 * 1024 * 1024, f"invalid {name}")
    for name in ("abs_tolerance", "rel_tolerance"):
        value = options[name]
        contract.require(type(value) in {int, float} and math.isfinite(value) and value >= 0, f"invalid {name}")
    contract.text(options["encoding"], "encoding")
    contract.require(options["length_unit"] in {None, "m", "cm", "mm", "in", "ft"}, "invalid length unit")
    contract.require(options["time_unit"] in {None, "s", "ms", "us", "ns"}, "invalid time unit")
    contract.require(options["time_order"] in {"strict", "nondecreasing"}, "invalid time order")
    contract.require(options["time_column"] is None or isinstance(options["time_column"], str), "invalid time column")


def source_entry(name, raw):
    return {"path": name, "role": "source", "sha256": contract.digest(raw), "size_bytes": len(raw)}


def claim_values(result, source_name):
    if result is None:
        return []
    claims = []
    for key, value in sorted(result.metrics.items()):
        claims.append({"id": key, "kind": "computed", "status": "known", "value": value, "unit": None,
                       "basis": [{"path": source_name, "locator": {"scope": "declared adapter scope, entire source"},
                                  "method": f"{TOOL}/{adapters.VERSION}; see data/parsed.json locators and receipts/parse.json"}],
                       "reason": None})
    if "length_unit" in result.data:
        unit = result.data["length_unit"]
        claims.append({"id": "length_unit", "kind": "source_declared", "status": "known" if unit else "unknown",
                       "value": unit, "unit": None,
                       "basis": [{"path": "receipts/parse.json", "locator": {"field": "options.length_unit"},
                                  "method": "caller declaration; not inferred from STL/OBJ"}] if unit else [],
                       "reason": None if unit else "Source format does not declare a length unit; caller supplied none."})
    return claims


def render_asset(object_id, fmt, metrics, limitations, source_name, error):
    lines = [f"# Engineering input {json.dumps(object_id, ensure_ascii=False)}", "",
             f"Format: {fmt}. Adapter: {TOOL}/{adapters.VERSION}.",
             f"Source: [{source_name}]({source_name}).", "",
             "## Parsed metrics", "", "```json", json.dumps(metrics, ensure_ascii=False, sort_keys=True, indent=2),
             "```", "", "[Facts](facts.json) · [Observations](observations.json) · [Execution](receipts/parse.json)", ""]
    if error is None:
        lines.extend(["[Complete extracted representation](data/parsed.json)", ""])
    else:
        lines.extend(["## Parsing failed", "", str(error), ""])
    lines.extend(["## Scope and limitations", ""])
    lines.extend("- " + item for item in limitations)
    lines.append("- No physical performance or real-world truth claim; no perceptual review was performed by this parser.")
    return "\n".join(lines) + "\n"


def seal(root, identity, report):
    files = []
    role_names = {"profile.json": "profile", "facts.json": "facts", "observations.json": "observations", "asset.md": "asset"}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in {"manifest.json", "acceptance.json"}:
            continue
        name = path.relative_to(root).as_posix()
        role = role_names.get(name, "source" if name.startswith("source/") else
                              "receipt" if name.startswith("receipts/") else "evidence")
        raw = path.read_bytes()
        files.append({"path": name, "role": role, "sha256": contract.digest(raw), "size_bytes": len(raw)})
    write_json(root, "manifest.json", {"schema_version": "general-parser.manifest.v1",
                                     "object_id": identity["object_id"], "version": identity["version"], "files": files})
    report["manifest_sha256"] = contract.digest((root / "manifest.json").read_bytes())
    write_json(root, "acceptance.json", report)


def build(source, destination, fmt=None, options=None, object_id=None, version="v1"):
    source, destination = Path(source), Path(destination)
    contract.require(source.is_file(), "Input must be a file")
    contract.require(not destination.exists(), "Output version already exists; choose a new destination")
    options = dict(DEFAULT_OPTIONS if options is None else options)
    validate_options(options)
    fmt = fmt or source.suffix.lower().lstrip(".")
    if fmt not in adapters.FORMATS:
        raise adapters.Unsupported(f"No implemented adapter for {fmt}; use --list-formats or a verified external adapter")
    contract.require(source.stat().st_size <= options["max_bytes"], "Input byte limit exceeded")
    raw = source.read_bytes()
    object_id = object_id or (re.sub(r"[^a-zA-Z0-9_-]", "-", source.stem).strip("-")[:60] or "input") + "-" + contract.digest(raw)[:8]
    contract.require(bool(re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", object_id)), "Invalid object_id")
    contract.require(bool(re.fullmatch(r"[a-zA-Z0-9_.-]{1,64}", version)) and version not in {".", ".."}, "Invalid version")
    source_name = "source/input." + fmt
    result, error = None, None
    try:
        result = adapters.parse(raw, fmt, options)
    except (adapters.ParseError, ValueError, RecursionError) as exc:
        error = exc
    native_checks = result.checks if result else []
    required = ["content.fidelity", "content.coverage", "document.consistency", "engineering.replay"]
    required += [item["id"] for item in native_checks]
    if options["require_observation"]:
        required.append("observation.consistency")
    profile = {
        "schema_version": "general-parser.profile.v1", "id": "engineering." + fmt + ".v1", "format": fmt,
        "output_language": "en", "parse_owner": "local", "summary_owner": "none",
        "observation_policy": "required" if options["require_observation"] else "not_applicable",
        "adapter": {"tool": TOOL, "version": adapters.VERSION, "python_version": platform.python_version(),
                    "implementation_sha256": implementation_hash(), "options": options,
                    "scope": adapters.FORMATS[fmt], "source_name": source_name, "original_filename": source.name},
        "roles": {"facts": "facts.json", "observations": "observations.json", "asset": "asset.md"},
        "required_checks": required, "publication_checks": [],
    }
    identity = {"object_id": object_id, "version": version,
                "profile_sha256": contract.digest(json_bytes(profile)),
                "source_manifest_sha256": contract.source_digest([source_entry(source_name, raw)])}
    metrics = result.metrics if result else {}
    limitations = list(result.limitations if result else ["Parsing failed; no accepted extracted content."])
    if options["require_observation"]:
        limitations.append("Requested perceptual review is pending; an agent must actually inspect the evidence.")
    facts = {"schema_version": "general-parser.facts.v1", **identity,
             "extraction": {"status": "unsupported" if isinstance(error, adapters.Unsupported) else "failed" if error else "succeeded",
                            "tool": TOOL, "tool_version": adapters.VERSION, "receipt": "receipts/parse.json", "losses": []},
             "claims": claim_values(result, source_name), "diagnostics": [str(error)] if error else [],
             "limitations": limitations}
    observation = {"schema_version": "general-parser.observations.v1", **identity,
                   "review_status": "not_run" if options["require_observation"] else "skipped", "observer": None,
                   "observed_at": None, "items": [], "hypotheses": [],
                   "reason": "This adapter performs structural/numeric extraction; it has not viewed or listened to evidence."}
    asset = render_asset(object_id, fmt, metrics, limitations, source_name, error)
    content_checks = []
    if result:
        replay = adapters.parse(raw, fmt, options)
        same = contract.canonical({"data": replay.data, "metrics": replay.metrics}) == contract.canonical({"data": result.data, "metrics": result.metrics})
        content_checks = [
            adapters.check("content.fidelity", True, "Run format value checks; preserve full declared representation and source locators"),
            adapters.check("content.coverage", True, "Consume full source within declared adapter scope; never silently truncate on limits"),
            adapters.check("document.consistency", True, "Generate facts and asset from the same metrics; readback verified before commit"),
            adapters.check("engineering.replay", same, "Reparse immutable source and compare full representation and metrics"),
        ] + native_checks
    checks = []
    by_id = {item["id"]: item for item in content_checks}
    for cid in required:
        item = by_id.get(cid)
        checks.append({"id": cid, "executed": item["executed"] if item else False,
                       "result": item["result"] if item else "unknown", "method": item["method"] if item else None,
                       "evidence": ["receipts/checks.json"] if item else [],
                       "reason": None if item and item["result"] == "pass" else
                                 "Check failed; see actual/expected evidence." if item else
                                 "Perceptual review has not run." if cid == "observation.consistency" else str(error)})
    if error:
        state = "unsupported" if isinstance(error, adapters.Unsupported) else "failed"
    elif any(item["result"] == "fail" for item in checks):
        state = "failed"
    elif options["require_observation"]:
        state = "visual_review_required"
    else:
        state = "local_ready_with_limitations" if limitations else "local_ready"
    report = {"schema_version": "general-parser.acceptance.v1", **identity, "manifest_sha256": "",
              "state": state, "checks": checks, "limitations": limitations}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".engineering-staging-", dir=destination.parent) as directory:
        root = Path(directory)
        (root / "source").mkdir()
        (root / source_name).write_bytes(raw)
        write_json(root, "profile.json", profile)
        write_json(root, "facts.json", facts)
        write_json(root, "observations.json", observation)
        (root / "asset.md").write_text(asset, encoding="utf-8")
        if result:
            write_json(root, "data/parsed.json", {"schema_version": "general-parser.data.v1", "format": fmt,
                                                "data": result.data, "metrics": result.metrics})
        write_json(root, "receipts/parse.json", {"tool": TOOL, "version": adapters.VERSION, "format": fmt, "options": options,
                                               "source_sha256": contract.digest(raw), "scope": adapters.FORMATS[fmt],
                                               "status": facts["extraction"]["status"], "error": str(error) if error else None})
        write_json(root, "receipts/checks.json", {"checks": content_checks, "coverage": "declared scope only",
                                                "perception_executed": False})
        seal(root, identity, report)
        contract.verify(root)
        if state in contract.READY:
            verify_content(root, require_ready=True)
        contract.require(not destination.exists(), "Output appeared during parsing; refusing replacement")
        root.rename(destination)
    return {"output": str(destination), "state": state, "format": fmt, "object_id": object_id,
            "checks_passed": state in contract.READY, "error": str(error) if error else None}


def verify_content(root, require_ready=False):
    root = Path(root).resolve()
    structure = contract.verify(root, require_ready=require_ready)
    profile = contract.strict_json((root / "profile.json").read_bytes())
    adapter = contract.obj(profile.get("adapter"), "adapter")
    contract.require(adapter.get("tool") == TOOL and adapter.get("version") == adapters.VERSION, "Not a supported executable adapter bundle")
    contract.require(adapter.get("implementation_sha256") == implementation_hash(), "Adapter implementation changed; revalidate as a new version")
    options = adapter["options"]
    validate_options(options)
    fmt = profile["format"]
    contract.require(fmt in adapters.FORMATS, "Adapter is not registered")
    source_name = adapter["source_name"]
    manifest = contract.strict_json((root / "manifest.json").read_bytes())
    contract.require(any(item["path"] == source_name and item["role"] == "source" for item in manifest["files"]),
                     "Replay input must be a declared source")
    raw = contract.safe_path(root, source_name).read_bytes()
    result = adapters.parse(raw, fmt, options)
    actual = contract.strict_json((root / "data/parsed.json").read_bytes())
    expected = {"schema_version": "general-parser.data.v1", "format": fmt, "data": result.data, "metrics": result.metrics}
    contract.require(actual == expected, "Extracted data differs from fresh source replay")
    facts = contract.strict_json(contract.safe_path(root, profile["roles"]["facts"]).read_bytes())
    contract.require(facts.get("claims") == claim_values(result, source_name), "Facts differ from fresh source replay")
    report = contract.strict_json((root / "acceptance.json").read_bytes())
    asset = render_asset(report["object_id"], fmt, result.metrics, facts["limitations"], source_name, None)
    contract.require(contract.safe_path(root, profile["roles"]["asset"]).read_text(encoding="utf-8") == asset, "Document differs from verified projection")
    failed = [item["id"] for item in result.checks if item["result"] != "pass"]
    contract.require(not failed, "Executable format checks failed: " + ", ".join(failed))
    return {**structure, "source_replay_validation": "pass", "format_checks": [item["id"] for item in result.checks],
            "semantic_validation": "declared structural/numeric scope checked; no real-world/perceptual validation"}
