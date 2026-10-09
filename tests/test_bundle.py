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


if __name__ == "__main__":
    unittest.main()
