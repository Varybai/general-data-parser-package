import tempfile
from pathlib import Path
import unittest

from bundle_fixture import dump, load, make_bundle, refresh, verifier


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = make_bundle(Path(self.tmp.name) / "object")

    def rejects(self, message=None):
        with self.assertRaisesRegex(verifier.InvalidBundle, message or ".*"):
            verifier.verify(self.root, require_ready=True)

    def test_valid_real_local_formats(self):
        for kind in ("csv", "json", "md"):
            with self.subTest(kind=kind):
                root = make_bundle(Path(self.tmp.name) / kind, kind)
                result = verifier.verify(root, True)
                self.assertTrue(result["recorded_required_checks_passed"])
                self.assertEqual(result["semantic_validation"], "not_performed_by_this_verifier")

    def test_source_tamper(self):
        (self.root / "source/input.csv").write_text("changed")
        self.rejects("file bytes changed")

    def test_changed_profile_invalidates_binding(self):
        profile = load(self.root, "profile.json")
        profile["adapter"]["version"] = "changed"
        dump(self.root, "profile.json", profile)
        refresh(self.root, rebind=False)
        self.rejects("profile binding")

    def test_stale_source_binding(self):
        facts = load(self.root, "facts.json")
        facts["source_manifest_sha256"] = "0" * 64
        dump(self.root, "facts.json", facts)
        refresh(self.root, rebind=False)
        self.rejects("source binding")

    def test_wrong_object_version(self):
        facts = load(self.root, "facts.json")
        facts["version"] = "v2"
        dump(self.root, "facts.json", facts)
        refresh(self.root)
        self.rejects("object/version")

    def test_overview_drift(self):
        (self.root / ".overview.md").write_text("different document")
        refresh(self.root)
        self.rejects("asset/overview")

    def test_failed_required_check_blocks_ready(self):
        report = load(self.root, "acceptance.json")
        report["checks"][0].update(result="fail", reason="source mismatch")
        dump(self.root, "acceptance.json", report)
        self.rejects("nonpassing required")

    def test_prepared_is_not_ready(self):
        report = load(self.root, "acceptance.json")
        report["state"] = "prepared"
        report["checks"][0].update(result="unknown", executed=False, evidence=[], reason="not checked")
        dump(self.root, "acceptance.json", report)
        self.assertFalse(verifier.verify(self.root)["recorded_required_checks_passed"])
        self.rejects("not ready")

    def test_pass_without_execution_rejected(self):
        report = load(self.root, "acceptance.json")
        report["checks"][0]["executed"] = False
        dump(self.root, "acceptance.json", report)
        self.rejects("executed evidence")

    def test_missing_receipt_rejected(self):
        report = load(self.root, "acceptance.json")
        report["checks"][0]["evidence"] = ["receipts/missing.json"]
        dump(self.root, "acceptance.json", report)
        self.rejects("unlisted evidence")

    def test_cannot_drop_core_gates(self):
        profile = load(self.root, "profile.json")
        profile["required_checks"] = ["format.csv"]
        dump(self.root, "profile.json", profile)
        refresh(self.root)
        self.rejects("core checks")

    def test_required_observation_unread(self):
        self.root = make_bundle(Path(self.tmp.name) / "review", reviewed=True)
        obs = load(self.root, "observations.json")
        obs.update(review_status="not_run", items=[], reason="not read")
        dump(self.root, "observations.json", obs)
        refresh(self.root)
        self.rejects("not reviewed")

    def test_real_read_record_does_not_override_failed_content_check(self):
        self.root = make_bundle(Path(self.tmp.name) / "review", reviewed=True)
        report = load(self.root, "acceptance.json")
        report["checks"][-1].update(result="fail", reason="description contradicts source geometry")
        dump(self.root, "acceptance.json", report)
        self.rejects("nonpassing required")

    def test_observation_requires_timezone(self):
        self.root = make_bundle(Path(self.tmp.name) / "review", reviewed=True)
        obs = load(self.root, "observations.json")
        obs["observed_at"] = "2026-10-09T00:00:00"
        dump(self.root, "observations.json", obs)
        refresh(self.root)
        self.rejects("timezone")

    def test_known_fact_requires_source_basis(self):
        facts = load(self.root, "facts.json")
        facts["claims"][0]["basis"] = []
        dump(self.root, "facts.json", facts)
        refresh(self.root)
        self.rejects("basis")

    def test_unknown_is_not_zero(self):
        facts = load(self.root, "facts.json")
        facts["claims"][1].update(status="unknown", value=0, reason="unavailable")
        dump(self.root, "facts.json", facts)
        refresh(self.root)
        self.rejects("must be null")

    def test_partial_requires_disclosure(self):
        facts = load(self.root, "facts.json")
        facts["extraction"]["status"] = "partial"
        dump(self.root, "facts.json", facts)
        refresh(self.root)
        self.rejects("limitations")
        report = load(self.root, "acceptance.json")
        report.update(state="local_ready_with_limitations", limitations=["Optional fields unavailable; required coverage checked."])
        dump(self.root, "acceptance.json", report)
        self.assertTrue(verifier.verify(self.root, True)["recorded_required_checks_passed"])

    def test_published_requires_remote_evidence(self):
        report = load(self.root, "acceptance.json")
        report["state"] = "published"
        dump(self.root, "acceptance.json", report)
        self.rejects("remote gates")

    def test_unlisted_file(self):
        (self.root / "extra.txt").write_text("unexpected")
        self.rejects("unlisted/missing")

    def test_path_traversal(self):
        manifest = load(self.root, "manifest.json")
        manifest["files"][0]["path"] = "../outside"
        dump(self.root, "manifest.json", manifest)
        self.rejects("unsafe path")

    def test_symlink(self):
        (self.root / "link").symlink_to(self.root / "source/input.csv")
        self.rejects("symlink")

    def test_changed_receipt(self):
        (self.root / "receipts/content-check.json").write_text('{}')
        self.rejects("file bytes changed")

    def test_stale_manifest_report(self):
        report = load(self.root, "acceptance.json")
        report["manifest_sha256"] = "0" * 64
        dump(self.root, "acceptance.json", report)
        self.rejects("manifest binding")

    def test_nonstandard_json_is_rejected(self):
        for raw in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}'):
            with self.subTest(raw=raw), self.assertRaises(verifier.InvalidBundle):
                verifier.strict_json(raw)

    def test_role_remapping(self):
        profile = load(self.root, "profile.json")
        (self.root / "facts.json").rename(self.root / "data.json")
        profile["roles"]["facts"] = "data.json"
        dump(self.root, "profile.json", profile)
        refresh(self.root)
        self.assertTrue(verifier.verify(self.root, True)["recorded_required_checks_passed"])

    def configure_external_summaries(self, owner="backend"):
        profile = load(self.root, "profile.json")
        profile["summary_owner"] = owner
        if owner == "backend":
            profile["backend"] = "openviking"
            profile["publication_checks"] = [
                "remote.bytes", "remote.index", "remote.query", "remote.summaries"
            ]
        profile.pop("overview_relation")
        for role in ("abstract", "overview"):
            (self.root / profile["roles"].pop(role)).unlink()
        dump(self.root, "profile.json", profile)
        refresh(self.root)

    def record_publication_checks(self, summary_result="pass"):
        # Simulated receipts test gate semantics, not a live OpenViking service.
        dump(self.root, "receipts/backend.json", {
            "test_only": True, "abstract_uri": "viking://resources/fixture/.abstract.md",
            "overview_uri": "viking://resources/fixture/.overview.md",
            "readback": "simulated"
        })
        report = load(self.root, "acceptance.json")
        for cid in load(self.root, "profile.json")["publication_checks"]:
            result = summary_result if cid == "remote.summaries" else "pass"
            report["checks"].append({
                "id": cid, "executed": result == "pass", "result": result,
                "method": "simulated backend contract check",
                "evidence": ["receipts/backend.json"] if result == "pass" else [],
                "reason": None if result == "pass" else "backend summaries still pending",
            })
        dump(self.root, "acceptance.json", report)
        refresh(self.root)

    def test_ordinary_parsing_needs_no_summaries(self):
        self.configure_external_summaries("none")
        result = verifier.verify(self.root, True)
        self.assertEqual(result["summary_owner"], "none")
        self.assertFalse((self.root / ".overview.md").exists())

    def test_ov_local_ready_precedes_backend_generation(self):
        self.configure_external_summaries()
        self.assertTrue(verifier.verify(self.root, True)["recorded_required_checks_passed"])

    def test_future_publication_checks_do_not_block_local_ready(self):
        self.configure_external_summaries()
        self.record_publication_checks("unknown")
        self.assertTrue(verifier.verify(self.root, True)["recorded_required_checks_passed"])

    def test_backend_owner_rejects_prefabricated_summary_role(self):
        self.configure_external_summaries()
        profile = load(self.root, "profile.json")
        profile["roles"]["overview"] = ".overview.md"
        dump(self.root, "profile.json", profile)
        (self.root / ".overview.md").write_text("prefabricated")
        refresh(self.root)
        self.rejects("summary files conflict")

    def test_backend_managed_filename_cannot_hide_as_receipt(self):
        self.configure_external_summaries()
        (self.root / ".abstract.md").write_text("prefabricated")
        refresh(self.root)
        self.rejects("must not be a local output")

    def test_ov_owner_cannot_be_local(self):
        profile = load(self.root, "profile.json")
        profile["backend"] = "openviking"
        dump(self.root, "profile.json", profile)
        refresh(self.root)
        self.rejects("OpenViking owns")

    def test_backend_published_requires_summary_gate(self):
        self.configure_external_summaries()
        profile = load(self.root, "profile.json")
        profile["publication_checks"].remove("remote.summaries")
        dump(self.root, "profile.json", profile)
        self.record_publication_checks()
        report = load(self.root, "acceptance.json")
        report["state"] = "published"
        dump(self.root, "acceptance.json", report)
        self.rejects("summary readback gate")

    def test_backend_pending_summaries_block_published(self):
        self.configure_external_summaries()
        self.record_publication_checks("unknown")
        report = load(self.root, "acceptance.json")
        report["state"] = "published"
        dump(self.root, "acceptance.json", report)
        self.rejects("nonpassing required")

    def test_backend_readback_can_complete_publication(self):
        self.configure_external_summaries()
        self.record_publication_checks()
        report = load(self.root, "acceptance.json")
        report["state"] = "published"
        dump(self.root, "acceptance.json", report)
        result = verifier.verify(self.root, True)
        self.assertEqual(result["declared_state"], "published")

    def test_legacy_010_local_profile_still_valid(self):
        profile = load(self.root, "profile.json")
        profile.pop("summary_owner")
        dump(self.root, "profile.json", profile)
        refresh(self.root)
        self.assertEqual(verifier.verify(self.root, True)["summary_owner"], "local")

    def configure_backend_parsing(self):
        profile = load(self.root, "profile.json")
        for name in profile["roles"].values():
            (self.root / name).unlink()
        for path in (self.root / "receipts").iterdir():
            path.unlink()
        profile.update(parse_owner="backend", backend="openviking", summary_owner="backend", roles={},
                       required_checks=["input.integrity", "backend.capability"],
                       publication_checks=["remote.bytes", "remote.index", "remote.query",
                                           "remote.parse", "remote.summaries", "content.fidelity",
                                           "content.coverage", "document.consistency"])
        profile.pop("overview_relation")
        profile["adapter"] = {"tool": "OpenViking configured route", "version": "fixture"}
        dump(self.root, "profile.json", profile)
        dump(self.root, "receipts/native.json", {"test_only": True, "backend": "openviking"})
        report = load(self.root, "acceptance.json")
        report["state"] = "ready_to_submit"
        report["checks"] = [{
            "id": cid, "executed": True, "result": "pass", "method": "simulated backend preflight",
            "evidence": ["receipts/native.json"], "reason": None
        } for cid in profile["required_checks"]]
        dump(self.root, "acceptance.json", report)
        refresh(self.root)

    def complete_backend_parsing(self, parse_result="pass"):
        profile = load(self.root, "profile.json")
        report = load(self.root, "acceptance.json")
        report["state"] = "published"
        for cid in profile["publication_checks"]:
            result = parse_result if cid == "remote.parse" else "pass"
            report["checks"].append({
                "id": cid, "executed": result == "pass", "result": result,
                "method": "simulated native parse and readback",
                "evidence": ["receipts/native.json"] if result == "pass" else [],
                "reason": None if result == "pass" else "parse task still pending"
            })
        dump(self.root, "acceptance.json", report)

    def test_backend_parsing_accepts_source_and_receipts_only(self):
        self.configure_backend_parsing()
        result = verifier.verify(self.root)
        self.assertEqual(result["parse_owner"], "backend")
        self.assertEqual(result["declared_state"], "ready_to_submit")
        self.assertFalse((self.root / "facts.json").exists())
        self.assertFalse((self.root / "asset.md").exists())
        self.rejects("not yet completed")

    def test_backend_input_cannot_claim_local_parse_completed(self):
        self.configure_backend_parsing()
        report = load(self.root, "acceptance.json")
        report["state"] = "local_ready"
        dump(self.root, "acceptance.json", report)
        self.rejects("not local parsing completion")

    def test_backend_capability_failure_blocks_submission_ready(self):
        self.configure_backend_parsing()
        report = load(self.root, "acceptance.json")
        report["checks"][1].update(result="unsupported", executed=False, evidence=[], reason="parser disabled")
        dump(self.root, "acceptance.json", report)
        self.rejects("nonpassing required")

    def test_backend_parse_pending_blocks_published(self):
        self.configure_backend_parsing()
        self.complete_backend_parsing("unknown")
        self.rejects("nonpassing required")

    def test_backend_native_readback_can_complete_without_local_documents(self):
        self.configure_backend_parsing()
        self.complete_backend_parsing()
        result = verifier.verify(self.root, True)
        self.assertEqual(result["declared_state"], "published")
        self.assertFalse((self.root / ".overview.md").exists())

    def test_backend_publication_requires_content_checks(self):
        self.configure_backend_parsing()
        profile = load(self.root, "profile.json")
        profile["publication_checks"].remove("content.coverage")
        dump(self.root, "profile.json", profile)
        refresh(self.root)
        self.complete_backend_parsing()
        self.rejects("parsing/content/readback gates")

    def test_backend_rejects_local_parsed_artifact(self):
        self.configure_backend_parsing()
        profile = load(self.root, "profile.json")
        profile["roles"]["asset"] = "asset.md"
        dump(self.root, "profile.json", profile)
        (self.root / "asset.md").write_text("duplicate locally parsed document")
        refresh(self.root)
        self.rejects("roles must be empty")

    def test_backend_perception_checks_run_after_submission(self):
        self.configure_backend_parsing()
        profile = load(self.root, "profile.json")
        profile["observation_policy"] = "required"
        dump(self.root, "profile.json", profile)
        refresh(self.root)
        self.complete_backend_parsing()
        self.rejects("parsing/content/readback gates")

    def test_explicit_ov_local_parsing_requires_a_reason(self):
        self.configure_external_summaries()
        profile = load(self.root, "profile.json")
        profile["parse_owner"] = "local"
        dump(self.root, "profile.json", profile)
        refresh(self.root)
        self.rejects("scope or capability reason")
        profile["local_parse_reason"] = "requested_additional_extraction"
        dump(self.root, "profile.json", profile)
        refresh(self.root)
        self.assertTrue(verifier.verify(self.root, True)["recorded_required_checks_passed"])

    def test_backend_quality_checks_are_not_input_preflight(self):
        self.configure_backend_parsing()
        profile = load(self.root, "profile.json")
        profile["required_checks"].append("content.fidelity")
        dump(self.root, "profile.json", profile)
        refresh(self.root)
        self.rejects("belong after submission")


if __name__ == "__main__":
    unittest.main()
