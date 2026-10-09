#!/usr/bin/env python3
"""Read-only integrity and recorded-gate verifier; Python 3.10+, stdlib only.

This verifies evidence bindings, not the truth or execution of reported actions.
"""

import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys


BASE_TEXT_ROLES = {"facts", "observations", "asset"}
SUMMARY_ROLES = {"abstract", "overview"}
TEXT_ROLES = BASE_TEXT_ROLES | SUMMARY_ROLES
ROLES = TEXT_ROLES | {"profile", "source", "dependency", "evidence", "receipt"}
CORE_CHECKS = {"content.fidelity", "content.coverage", "document.consistency"}
REMOTE_CHECKS = {"remote.bytes", "remote.index", "remote.query"}
READY = {"local_ready", "local_ready_with_limitations", "published"}
STATES = READY | {
    "prepared", "visual_review_required", "failed", "unsupported", "conflict",
    "remote_unknown", "remote_incomplete", "invalidated", "ready_to_submit",
}
CONTROL = {"manifest.json", "acceptance.json"}
SHA = re.compile(r"[0-9a-f]{64}\Z")


class InvalidBundle(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InvalidBundle(message)


def text(value, name):
    require(isinstance(value, str) and bool(value.strip()), f"{name}: nonempty string required")
    return value


def obj(value, name):
    require(isinstance(value, dict), f"{name}: object required")
    return value


def array(value, name):
    require(isinstance(value, list), f"{name}: array required")
    return value


def strings(value, name):
    return [text(item, name) for item in array(value, name)]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def source_digest(files):
    rows = [{key: entry[key] for key in ("path", "role", "sha256")}
            for entry in files if entry["role"] in {"source", "dependency"}]
    return digest(canonical(sorted(rows, key=lambda entry: entry["path"])))


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result

    def number(value):
        result = float(value)
        require(math.isfinite(result), "nonfinite JSON number")
        return result

    def constant(value):
        raise InvalidBundle(f"nonstandard JSON constant: {value}")

    return obj(json.loads(raw, object_pairs_hook=pairs, parse_float=number,
                          parse_constant=constant), "JSON root")


def safe_path(root, value):
    value = text(value, "path")
    path = PurePosixPath(value)
    require("\\" not in value and "\x00" not in value and not path.is_absolute()
            and path.as_posix() == value and path.parts
            and all(part not in {".", ".."} for part in path.parts), f"unsafe path: {value}")
    candidate = root
    for part in path.parts:
        candidate = candidate / part
        require(not candidate.is_symlink(), f"symlink rejected: {value}")
    require(candidate.resolve().is_relative_to(root), f"escaping path: {value}")
    return candidate


def file_digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_checks(report, ref):
    checks = {}
    for check in array(report.get("checks"), "checks"):
        obj(check, "check")
        cid = text(check.get("id"), "check id")
        require(cid not in checks, f"duplicate check: {cid}")
        require(type(check.get("executed")) is bool, "executed must be boolean")
        result = check.get("result")
        require(result in {"pass", "fail", "unknown", "skipped", "unsupported"}, "invalid check result")
        evidence = strings(check.get("evidence"), "check evidence")
        for name in evidence:
            ref(name, {"receipt"})
        if result == "pass":
            require(check["executed"] and bool(evidence), "pass requires executed evidence")
            text(check.get("method"), "check method")
        else:
            text(check.get("reason"), "nonpass reason")
        checks[cid] = check
    return checks


def verify_backend_input(root, profile, manifest_raw, entries, identity, roles, files, ref, require_ready):
    """A source-and-receipt package delegates actual parsing to the backend."""
    text(profile.get("backend"), "backend")
    require(obj(profile.get("roles"), "profile.roles") == {}, "backend parsing roles must be empty")
    require(not TEXT_ROLES.intersection(roles), "backend parsing must not require local parsed documents")
    for name, entry in files.items():
        if entry["role"] not in {"source", "dependency"}:
            require(PurePosixPath(name).name not in {
                "facts.json", "observations.json", "asset.md", ".abstract.md", ".overview.md"
            }, "native backend output must be stored as a receipt, not prefabricated")
    owner = profile.get("summary_owner")
    require(owner in {"none", "backend"}, "backend parsing cannot own local summaries")
    if profile["backend"].casefold() in {"ov", "openviking"}:
        require(owner == "backend", "OpenViking owns its generated summaries")
    require("overview_relation" not in profile and "overview_rule" not in profile,
            "local overview relation forbidden for backend parsing")
    policy = profile.get("observation_policy")
    require(policy in {"required", "optional", "not_applicable"}, "invalid observation policy")
    required_list = strings(profile.get("required_checks"), "required_checks")
    required = set(required_list)
    require(len(required) == len(required_list) and {"input.integrity", "backend.capability"} <= required,
            "backend parsing requires input and capability gates")
    require(not (CORE_CHECKS | REMOTE_CHECKS | {"remote.parse", "remote.summaries", "observation.consistency"}) & required,
            "backend content and publication checks belong after submission")
    publication_list = strings(profile.get("publication_checks"), "publication_checks")
    publication = set(publication_list)
    require(len(publication) == len(publication_list), "duplicate publication checks")
    report = strict_json(safe_path(root, "acceptance.json").read_bytes())
    require(report.get("schema_version") == "general-parser.acceptance.v1", "acceptance schema mismatch")
    require(all(report.get(key) == value for key, value in identity.items()), "object/version mismatch")
    require(report.get("manifest_sha256") == digest(manifest_raw), "manifest binding mismatch")
    profile_raw = safe_path(root, roles["profile"][0]).read_bytes()
    require(report.get("profile_sha256") == digest(profile_raw), "profile binding mismatch")
    require(report.get("source_manifest_sha256") == source_digest(entries), "source binding mismatch")
    state = report.get("state")
    require(state in STATES, "invalid acceptance state")
    require(state not in {"local_ready", "local_ready_with_limitations"},
            "backend input readiness is not local parsing completion")
    strings(report.get("limitations"), "acceptance.limitations")
    checks = read_checks(report, ref)
    if state == "published":
        needed = REMOTE_CHECKS | CORE_CHECKS | {"remote.parse"}
        if owner == "backend":
            needed.add("remote.summaries")
        if policy == "required":
            needed.add("observation.consistency")
        require(needed <= publication, "backend publication lacks parsing/content/readback gates")
        required |= publication
    require(required <= set(checks), f"missing checks: {sorted(required - set(checks))}")
    passed = all(checks[cid]["result"] == "pass" for cid in required)
    if state in {"ready_to_submit", "published"}:
        require(passed, "backend readiness has nonpassing required checks")
    if require_ready:
        require(state == "published" and passed, "backend parsing not yet completed and verified")
    return {
        "structural_validation": "pass", "recorded_required_checks_passed": passed,
        "declared_state": state, "object_id": identity["object_id"], "version": identity["version"],
        "files_verified": len(files), "profile": profile["id"], "parse_owner": "backend",
        "summary_owner": owner, "semantic_validation": "not_performed_by_this_verifier",
    }


def verify(root, require_ready=False):
    root = Path(root).resolve()
    manifest_raw = safe_path(root, "manifest.json").read_bytes()
    manifest = strict_json(manifest_raw)
    require(manifest.get("schema_version") == "general-parser.manifest.v1", "manifest schema mismatch")
    identity = {key: text(manifest.get(key), key) for key in ("object_id", "version")}
    entries = array(manifest.get("files"), "manifest.files")
    files = {}
    roles = {}
    for entry in entries:
        obj(entry, "manifest entry")
        name = text(entry.get("path"), "manifest path")
        path = safe_path(root, name)
        require(name not in files and name not in CONTROL, f"duplicate/reserved path: {name}")
        role = text(entry.get("role"), "role")
        require(role in ROLES, f"unknown role: {role}")
        require(path.is_file(), f"missing file: {name}")
        expected = entry.get("sha256")
        require(isinstance(expected, str) and SHA.fullmatch(expected), f"invalid hash: {name}")
        require(type(entry.get("size_bytes")) is int and entry["size_bytes"] >= 0,
                f"invalid size: {name}")
        require(path.stat().st_size == entry["size_bytes"] and file_digest(path) == expected,
                f"file bytes changed: {name}")
        files[name] = entry
        roles.setdefault(role, []).append(name)
    actual = set()
    for path in root.rglob("*"):
        require(not path.is_symlink(), f"symlink rejected: {path.relative_to(root)}")
        if path.is_file() and path.relative_to(root).as_posix() not in CONTROL:
            actual.add(path.relative_to(root).as_posix())
    require(actual == set(files), f"unlisted/missing files: {sorted(actual ^ set(files))}")
    require(bool(roles.get("source")), "at least one source required")
    for role in {"profile"}:
        require(len(roles.get(role, [])) == 1, f"exactly one {role} file required")

    def read_role(role):
        return safe_path(root, roles[role][0]).read_bytes()

    def ref(name, allowed):
        require(isinstance(name, str) and name in files, f"unlisted evidence: {name}")
        require(files[name]["role"] in allowed, f"wrong evidence role: {name}")

    def basis(value):
        items = array(value, "basis")
        require(bool(items), "evidence basis required")
        for item in items:
            obj(item, "basis item")
            ref(item.get("path"), {"source", "dependency", "evidence", "receipt"})
            require(bool(obj(item.get("locator"), "locator")), "nonempty locator required")
            text(item.get("method"), "basis method")

    profile_raw = read_role("profile")
    profile = strict_json(profile_raw)
    require(profile.get("schema_version") == "general-parser.profile.v1", "profile schema mismatch")
    for key in ("id", "format", "output_language"):
        text(profile.get(key), f"profile.{key}")
    adapter = obj(profile.get("adapter"), "adapter")
    text(adapter.get("tool"), "adapter.tool")
    text(adapter.get("version"), "adapter.version")
    parse_owner = profile.get("parse_owner", "local")
    require(parse_owner in {"local", "backend"}, "invalid parse owner")
    if parse_owner == "backend":
        return verify_backend_input(root, profile, manifest_raw, entries, identity, roles, files, ref, require_ready)
    for role in BASE_TEXT_ROLES:
        require(len(roles.get(role, [])) == 1, f"exactly one {role} file required")
    if "parse_owner" in profile and profile.get("backend") in {"ov", "openviking"}:
        require(profile.get("local_parse_reason") in {
            "backend_unsupported", "backend_unavailable", "requested_additional_extraction", "user_requested_local"
        }, "local parsing for OV requires an explicit scope or capability reason")
    # Profiles from 0.1.0 implicitly requested local summaries.
    owner = profile.get("summary_owner", "local")
    require(owner in {"none", "local", "backend"}, "invalid summary owner")
    backend = profile.get("backend")
    if owner == "backend":
        text(backend, "summary backend")
    if isinstance(backend, str) and backend.casefold() in {"ov", "openviking"}:
        require(owner == "backend", "OpenViking owns its generated summaries")
    expected_roles = TEXT_ROLES if owner == "local" else BASE_TEXT_ROLES
    for role in SUMMARY_ROLES:
        expected_count = 1 if owner == "local" else 0
        require(len(roles.get(role, [])) == expected_count, "summary files conflict with summary owner")
    if owner != "local":
        for name, entry in files.items():
            if entry["role"] not in {"source", "dependency"}:
                require(PurePosixPath(name).name not in {".abstract.md", ".overview.md"},
                        "backend/unrequested summary must not be a local output")
    mapping = obj(profile.get("roles"), "profile.roles")
    require(set(mapping) == expected_roles, "profile.roles conflicts with summary owner")
    require(all(mapping[role] == roles[role][0] for role in expected_roles), "role mapping mismatch")
    policy = profile.get("observation_policy")
    require(policy in {"required", "optional", "not_applicable"}, "invalid observation policy")
    relation = profile.get("overview_relation")
    if owner == "local":
        require(relation in {"identical", "custom"}, "invalid overview relation")
        if relation == "custom":
            text(profile.get("overview_rule"), "custom overview_rule")
    else:
        require("overview_relation" not in profile and "overview_rule" not in profile,
                "local overview relation forbidden for this summary owner")
    required_list = strings(profile.get("required_checks"), "required_checks")
    required = set(required_list)
    require(len(required) == len(required_list) and CORE_CHECKS <= required, "missing/duplicate core checks")
    if policy == "required":
        require("observation.consistency" in required, "required observation consistency check missing")
    publication_list = strings(profile.get("publication_checks", []), "publication_checks")
    publication = set(publication_list)
    require(len(publication) == len(publication_list), "duplicate publication checks")
    profile_sha, source_sha = digest(profile_raw), source_digest(entries)

    def binding(value, schema):
        require(value.get("schema_version") == schema, f"schema mismatch: {schema}")
        require(all(value.get(key) == val for key, val in identity.items()), "object/version mismatch")
        require(value.get("profile_sha256") == profile_sha, "profile binding mismatch")
        require(value.get("source_manifest_sha256") == source_sha, "source binding mismatch")

    facts = strict_json(read_role("facts"))
    observation = strict_json(read_role("observations"))
    report = strict_json(safe_path(root, "acceptance.json").read_bytes())
    binding(facts, "general-parser.facts.v1")
    binding(observation, "general-parser.observations.v1")
    binding(report, "general-parser.acceptance.v1")
    require(report.get("manifest_sha256") == digest(manifest_raw), "manifest binding mismatch")
    extraction = obj(facts.get("extraction"), "extraction")
    require(extraction.get("status") in {"succeeded", "partial", "failed", "unsupported"}, "extraction status")
    for key in ("tool", "tool_version"):
        text(extraction.get(key), f"extraction.{key}")
    ref(extraction.get("receipt"), {"receipt"})
    array(extraction.get("losses"), "extraction.losses")
    array(facts.get("diagnostics"), "diagnostics")
    array(facts.get("limitations"), "facts.limitations")
    ids = set()
    for claim in array(facts.get("claims"), "claims"):
        obj(claim, "claim")
        cid = text(claim.get("id"), "claim id")
        require(cid not in ids, f"duplicate id: {cid}")
        ids.add(cid)
        require(claim.get("kind") in {"source_declared", "extracted", "computed"}, "claim kind")
        status = claim.get("status")
        require(status in {"known", "partial", "unknown", "unsupported", "not_applicable"}, "claim status")
        require("value" in claim and "unit" in claim, "claim value/unit missing")
        if status in {"known", "partial"}:
            basis(claim.get("basis"))
        else:
            require(claim["value"] is None, "unknown value must be null")
        if status != "known":
            text(claim.get("reason"), "claim reason")

    review = observation.get("review_status")
    require(review in {"reviewed", "not_run", "skipped", "failed"}, "review status")
    items = array(observation.get("items"), "observation.items")
    if review == "reviewed":
        observer = obj(observation.get("observer"), "observer")
        require(observer.get("kind") in {"model", "agent", "human"}, "observer kind")
        text(observer.get("id"), "observer.id")
        ref(observer.get("receipt"), {"receipt"})
        at = datetime.fromisoformat(text(observation.get("observed_at"), "observed_at").replace("Z", "+00:00"))
        require(at.utcoffset() is not None, "observation time requires timezone")
        require(bool(items), "reviewed observation requires items")
    else:
        text(observation.get("reason"), "unreviewed reason")
        require(not items, "unreviewed observation cannot contain observed items")
    if policy == "not_applicable":
        require(review == "skipped", "not_applicable observation must be skipped")
    for item in items:
        obj(item, "observation item")
        oid = text(item.get("id"), "observation id")
        require(oid not in ids, f"duplicate id: {oid}")
        ids.add(oid)
        require(item.get("kind") in {"visual", "audio", "layout", "semantic"}, "observation kind")
        text(item.get("text"), "observation text")
        basis(item.get("basis"))
        array(item.get("limitations"), "observation limitations")
    hypothesis_ids = set()
    for item in array(observation.get("hypotheses"), "hypotheses"):
        obj(item, "hypothesis")
        hid = text(item.get("id"), "hypothesis id")
        require(hid not in ids | hypothesis_ids, f"duplicate id: {hid}")
        hypothesis_ids.add(hid)
        require(item.get("status") in {"unverified", "unknown", "not_applicable"}, "hypothesis status")
        refs = strings(item.get("based_on"), "hypothesis.based_on")
        require(set(refs) <= ids, "unknown hypothesis basis")
        if item["status"] == "unverified":
            text(item.get("text"), "hypothesis text")
            require(bool(refs), "hypothesis requires basis")
        else:
            require(item.get("text") is None, "unknown hypothesis must be null")
            text(item.get("reason"), "hypothesis reason")

    for role in (("asset", "abstract", "overview") if owner == "local" else ("asset",)):
        text(read_role(role).decode("utf-8"), role)
    if relation == "identical":
        require(read_role("asset") == read_role("overview"), "asset/overview bytes differ")
    state = report.get("state")
    require(state in STATES, "invalid acceptance state")
    require(state != "ready_to_submit", "ready_to_submit belongs to backend parsing")
    limits = strings(report.get("limitations"), "acceptance.limitations")
    checks = read_checks(report, ref)
    if state == "published":
        require(REMOTE_CHECKS <= required | publication, "published profile lacks remote gates")
        if owner == "backend":
            require("remote.summaries" in required | publication, "published backend lacks summary readback gate")
        required |= publication
    require(required <= set(checks), f"missing checks: {sorted(required - set(checks))}")
    passed = all(checks[cid]["result"] == "pass" for cid in required)
    optional_gap = policy == "optional" and review != "reviewed"
    optional_gap |= any(c["result"] != "pass" for cid, c in checks.items()
                        if cid not in required | publication)
    partial = extraction["status"] == "partial"
    if state in READY:
        require(passed, "ready state has nonpassing required checks")
        require(extraction["status"] in {"succeeded", "partial"}, "ready extraction failed/unsupported")
        if policy == "required":
            require(review == "reviewed", "required observation not reviewed")
        if optional_gap or partial:
            require(state != "local_ready" and bool(limits), "partial/optional gap requires disclosed limitations")
        if state == "local_ready_with_limitations":
            require(bool(limits), "limited state requires limitations")
    if require_ready:
        require(state in READY and passed, "bundle not ready")
    return {
        "structural_validation": "pass", "recorded_required_checks_passed": passed,
        "declared_state": state, "object_id": identity["object_id"], "version": identity["version"],
        "files_verified": len(files), "profile": profile["id"],
        "summary_owner": owner, "parse_owner": "local",
        "semantic_validation": "not_performed_by_this_verifier",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    try:
        result = verify(args.bundle, args.require_ready)
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(json.dumps({"structural_validation": "fail", "error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
