"""Exercise actual adapters with independent fixtures, corruptions and replay."""

import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1] / "skills/general-data-parser/scripts"
sys.path.insert(0, str(SCRIPTS))

import engineering_runtime as runtime
import verify_bundle as contract


ASCII_STL = b"""solid triangle
facet normal 0 0 1
outer loop
vertex 0 0 0
vertex 2 0 0
vertex 0 3 0
endloop
endfacet
endsolid triangle
"""
OBJ = b"v 0 0 0\nv 2 0 0\nv 0 3 0\nf -3 -2 -1\n"


def binary_stl():
    # A binary STL is still binary when its header begins with 'solid'.
    return b"solid binary".ljust(80, b"\0") + struct.pack("<I", 1) + struct.pack(
        "<12fH", 0, 0, 1, 0, 0, 0, 2, 0, 0, 0, 3, 0, 0)


class EngineeringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.counter = 0

    def run_file(self, fmt, raw, **updates):
        self.counter += 1
        source = self.root / f"input-{self.counter}.{fmt}"
        source.write_bytes(raw if isinstance(raw, bytes) else raw.encode("utf-8"))
        destination = self.root / f"result-{self.counter}"
        result = runtime.build(source, destination, options={**runtime.DEFAULT_OPTIONS, **updates})
        data = json.loads((destination / "data/parsed.json").read_text()) if (destination / "data/parsed.json").exists() else None
        return destination, result, data

    def assert_failed(self, fmt, raw, **updates):
        destination, result, _ = self.run_file(fmt, raw, **updates)
        self.assertIn(result["state"], {"failed", "unsupported"})
        with self.assertRaises(contract.InvalidBundle):
            contract.verify(destination, require_ready=True)
        return result

    def test_csv_preserves_quotes_multiline_zero_and_empty(self):
        destination, result, data = self.run_file("csv", 'id,value,note\na,0,"two\nlines"\nb,,"comma, quote"\n')
        self.assertEqual(result["state"], "local_ready")
        rows = data["data"]["rows"]
        self.assertEqual(rows[0]["values"], ["a", "0", "two\nlines"])
        self.assertEqual(rows[0]["source_lines"], [2, 3])
        self.assertEqual(rows[1]["values"], ["b", "", "comma, quote"])
        self.assertEqual(data["metrics"]["record_count"], 2)
        runtime.verify_content(destination, True)

    def test_tsv_without_header(self):
        _, result, data = self.run_file("tsv", "1\t2\n3\t4\n", header=False)
        self.assertTrue(result["checks_passed"])
        self.assertEqual(data["data"]["columns"], ["column_1", "column_2"])
        self.assertEqual(data["data"]["rows"][0]["values"], ["1", "2"])

    def test_table_rejects_duplicate_columns_and_ragged_rows(self):
        for raw in ("a,a\n1,2\n", "a,b\n1\n", "a,b\n1,2,3\n"):
            with self.subTest(raw=raw):
                self.assert_failed("csv", raw)

    def test_numeric_nanosecond_time_axis_is_exact(self):
        _, result, data = self.run_file("csv", "time,v\n9007199254740993000,1\n9007199254740993001,2\n",
                                      time_column="time", time_unit="ns")
        self.assertTrue(result["checks_passed"])
        self.assertEqual(data["metrics"]["time_span_seconds"], "1E-9")
        self.assertEqual(data["data"]["time"]["seconds"][0], "9007199254.740993000")

    def test_iso_time_uses_offset_and_microseconds(self):
        _, result, data = self.run_file("csv", "time,v\n2026-10-09T08:00:00.000001+08:00,1\n2026-10-09T00:00:01.000002Z,2\n",
                                      time_column="time")
        self.assertTrue(result["checks_passed"])
        self.assertEqual(data["metrics"]["time_span_seconds"], "1.000001")

    def test_time_order_and_missing_values_fail(self):
        for raw in ("time,v\n2,a\n1,b\n", "time,v\n1,a\n1,b\n", "time,v\n1,a\n,b\n"):
            self.assert_failed("csv", raw, time_column="time", time_unit="s")

    def test_nondecreasing_time_allows_duplicates(self):
        _, result, _ = self.run_file("csv", "time,v\n1,a\n1,b\n", time_column="time", time_unit="s", time_order="nondecreasing")
        self.assertTrue(result["checks_passed"])

    def test_iso_submicrosecond_and_naive_times_do_not_silently_truncate(self):
        for value in ("2026-10-09T00:00:00.1234567Z", "2026-10-09T00:00:00"):
            self.assert_failed("csv", "time,v\n" + value + ",1\n", time_column="time")

    def test_json_keeps_large_integer_decimal_and_scalar_types(self):
        destination, result, data = self.run_file("json", '{"big":9007199254740993,"value":0.12345678901234567890123456789,"null":null,"zero":"0","flag":true,"empty":[]}')
        self.assertTrue(result["checks_passed"])
        record = data["data"]["records"][0]
        self.assertEqual(record["value"]["big"], "9007199254740993")
        self.assertEqual(record["value"]["value"], "0.12345678901234567890123456789")
        self.assertIsNone(record["value"]["null"])
        self.assertIs(record["value"]["flag"], True)
        self.assertEqual(record["value"]["empty"], [])
        self.assertEqual({v["pointer"] for v in record["numeric_tokens"]}, {"/big", "/value"})
        runtime.verify_content(destination, True)

    def test_json_pointer_escapes_and_unicode(self):
        _, _, data = self.run_file("json", '{"a/b":{"~字段":-0.0}}')
        self.assertEqual(data["data"]["records"][0]["numeric_tokens"][0]["pointer"], "/a~1b/~0字段")
        self.assertEqual(data["data"]["records"][0]["numeric_tokens"][0]["lexeme"], "-0.0")

    def test_json_rejects_duplicate_keys_nan_and_surrogates(self):
        for raw in ('{"a":1,"a":2}', '{"x":NaN}', '{"x":"\\ud800"}'):
            with self.subTest(raw=raw):
                self.assert_failed("json", raw)

    def test_jsonl_preserves_physical_lines_and_empty_stream(self):
        _, result, data = self.run_file("jsonl", '{"x":1}\n\n[0,null]\n')
        self.assertTrue(result["checks_passed"])
        self.assertEqual(data["metrics"]["record_count"], 2)
        self.assertEqual(data["data"]["records"][1]["source_lines"], [3, 3])
        _, result, data = self.run_file("jsonl", "\n")
        self.assertTrue(result["checks_passed"])
        self.assertEqual(data["metrics"]["record_count"], 0)

    def test_jsonl_bad_line_is_not_dropped(self):
        self.assert_failed("jsonl", '{"x":1}\nnot-json\n')

    def test_xml_preserves_namespaces_attributes_text_tail_and_comments(self):
        _, result, data = self.run_file("xml", '<r xmlns="urn:test" unit="mm">before<a value="0"/>tail<!--note--></r>')
        self.assertTrue(result["checks_passed"])
        nodes = data["data"]["nodes"]
        self.assertEqual(nodes[0]["tag"], "{urn:test}r")
        self.assertEqual(nodes[0]["attributes"], {"unit": "mm"})
        self.assertEqual(nodes[1]["tail"], "tail")
        self.assertEqual(nodes[2]["tag"], "#comment")
        self.assertEqual(data["metrics"]["element_count"], 2)

    def test_xml_rejects_dtd_and_invalid_input(self):
        self.assertEqual(self.assert_failed("xml", '<!DOCTYPE r [<!ENTITY a "x">]><r>&a;</r>')["state"], "unsupported")
        self.assert_failed("xml", "<r><a></r>")

    def test_xml_doctype_text_in_cdata_is_not_an_entity_declaration(self):
        _, result, data = self.run_file("xml", '<r><![CDATA[<!DOCTYPE not-a-declaration>]]></r>')
        self.assertTrue(result["checks_passed"])
        self.assertEqual(data["data"]["nodes"][0]["text"], "<!DOCTYPE not-a-declaration>")

    def test_ascii_stl_expected_triangle_bounds(self):
        destination, result, data = self.run_file("stl", ASCII_STL, length_unit="mm")
        self.assertTrue(result["checks_passed"])
        self.assertEqual(data["metrics"]["bbox"]["extent"], [2.0, 3.0, 0.0])
        self.assertEqual(data["metrics"]["face_count"], 1)
        self.assertEqual(data["data"]["vertices"][1]["locator"]["line"], 5)
        runtime.verify_content(destination, True)

    def test_binary_stl_solid_header_and_float_layout(self):
        _, result, data = self.run_file("stl", binary_stl(), length_unit="m")
        self.assertTrue(result["checks_passed"])
        self.assertEqual(data["data"]["metadata"]["encoding"], "binary")
        self.assertEqual(data["data"]["vertices"][0]["locator"]["byte_offset"], 96)
        self.assertEqual(data["metrics"]["bbox"]["max"], [2.0, 3.0, 0.0])

    def test_binary_stl_truncation_and_nan_fail(self):
        self.assert_failed("stl", binary_stl()[:-1])
        value = bytearray(binary_stl())
        struct.pack_into("<f", value, 96, float("nan"))
        self.assert_failed("stl", bytes(value))

    def test_mesh_unknown_unit_is_disclosed_or_blocks_requirement(self):
        _, result, data = self.run_file("obj", OBJ)
        self.assertEqual(result["state"], "local_ready_with_limitations")
        self.assertIsNone(data["data"]["length_unit"])
        self.assert_failed("obj", OBJ, require_unit=True)

    def test_obj_negative_indices_and_polygon_are_preserved(self):
        _, result, data = self.run_file("obj", OBJ, length_unit="mm")
        self.assertTrue(result["checks_passed"])
        self.assertEqual(data["data"]["faces"][0]["vertices"], [0, 1, 2])
        self.assertEqual(data["metrics"]["bbox"]["extent"], [2.0, 3.0, 0.0])
        _, _, quad = self.run_file("obj", "v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3 4\n")
        self.assertEqual(quad["data"]["faces"][0]["vertices"], [0, 1, 2, 3])

    def test_obj_invalid_refs_and_unhandled_geometry_fail(self):
        prefix = "v 0 0 0\nv 2 0 0\nv 0 3 0\n"
        for face in ("f 0 1 2", "f 1 2 9", "f 1/ 2/ 3/", "curv 0 1 1 2 3"):
            self.assert_failed("obj", prefix + face + "\n")

    def test_degenerate_mesh_fails_engineering_check(self):
        self.assert_failed("obj", "v 0 0 0\nv 1 0 0\nv 2 0 0\nf 1 2 3\n")

    def test_material_scope_is_retained_and_disclosed(self):
        _, result, data = self.run_file("obj", b"mtllib model.mtl\nusemtl red\n" + OBJ, length_unit="mm")
        self.assertEqual(result["state"], "local_ready_with_limitations")
        self.assertEqual(data["data"]["metadata"]["material_directives"][0]["values"], ["model.mtl"])

    def test_requested_perception_cannot_be_fabricated(self):
        destination, result, _ = self.run_file("stl", ASCII_STL, length_unit="mm", require_observation=True)
        self.assertEqual(result["state"], "visual_review_required")
        self.assertEqual(json.loads((destination / "observations.json").read_text())["review_status"], "not_run")
        with self.assertRaises(contract.InvalidBundle):
            runtime.verify_content(destination, True)

    def test_limits_fail_instead_of_truncating(self):
        self.assert_failed("csv", "a\n1\n2\n", max_items=2)
        self.assert_failed("obj", OBJ, max_items=2)

    def test_inapplicable_options_are_rejected(self):
        self.assert_failed("json", '{"x":1}', time_column="x")
        self.assert_failed("json", '{"x":1}', header=False)
        self.assert_failed("csv", "a\n1\n", length_unit="mm")

    def test_invalid_tolerance_rejected(self):
        with self.assertRaises(contract.InvalidBundle):
            self.run_file("obj", OBJ, abs_tolerance=float("nan"))

    def test_existing_output_is_not_overwritten(self):
        destination, _, _ = self.run_file("csv", "a\n1\n")
        previous = (destination / "manifest.json").read_bytes()
        with self.assertRaises(contract.InvalidBundle):
            runtime.build(self.root / "input-1.csv", destination)
        self.assertEqual((destination / "manifest.json").read_bytes(), previous)

    def reseal(self, root):
        report = json.loads((root / "acceptance.json").read_text())
        runtime.seal(root, report, report)

    def test_rehashed_corrupt_data_is_detected_by_source_replay(self):
        root, _, data = self.run_file("csv", "a,b\n1,2\n")
        data["data"]["rows"][0]["values"][0] = "999"
        runtime.write_json(root, "data/parsed.json", data)
        self.reseal(root)
        contract.verify(root, True)  # Hashes alone cannot prove source fidelity.
        with self.assertRaisesRegex(contract.InvalidBundle, "fresh source replay"):
            runtime.verify_content(root, True)

    def test_rehashed_facts_and_document_drift_are_detected(self):
        root, _, _ = self.run_file("obj", OBJ, length_unit="mm")
        facts = json.loads((root / "facts.json").read_text())
        facts["claims"][0]["value"] = "false"
        runtime.write_json(root, "facts.json", facts)
        self.reseal(root)
        with self.assertRaisesRegex(contract.InvalidBundle, "Facts differ"):
            runtime.verify_content(root, True)
        root, _, _ = self.run_file("csv", "a\n1\n")
        (root / "asset.md").write_text("wrong content")
        self.reseal(root)
        with self.assertRaisesRegex(contract.InvalidBundle, "Document differs"):
            runtime.verify_content(root, True)

    def test_cli_can_run_from_unrelated_directory(self):
        source = self.root / "sample.json"
        source.write_text('{"v":12345678901234567890}')
        output = self.root / "cli"
        result = subprocess.run([sys.executable, "-B", str(SCRIPTS / "parse_file.py"), str(source), "--output", str(output)],
                                cwd=self.root, text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout)["state"], "local_ready")
        verify = subprocess.run([sys.executable, "-B", str(SCRIPTS / "verify_engineering.py"), str(output), "--require-ready"],
                                cwd=self.root, text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(verify.stdout)["source_replay_validation"], "pass")


if __name__ == "__main__":
    unittest.main()
