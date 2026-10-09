#!/usr/bin/env python3
"""Run actual packaged parsers over small, independently checked engineering inputs."""

import argparse
import json
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parents[1] / "skills/general-data-parser/scripts"
sys.path.insert(0, str(SCRIPTS))
from engineering_runtime import DEFAULT_OPTIONS, build, verify_content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output must be a new directory")
    args.output.mkdir(parents=True)
    inputs = args.output / "inputs"
    inputs.mkdir()
    triangle = "solid t\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 2 0 0\nvertex 0 3 0\nendloop\nendfacet\nendsolid t\n"
    binary = b"solid binary".ljust(80, b"\0") + struct.pack("<I", 1) + struct.pack("<12fH", 0, 0, 1, 0, 0, 0, 2, 0, 0, 0, 3, 0, 0)
    fixtures = {
        "table.csv": ('time,value\n0,1.25\n1,0\n2,3.5\n', {"time_column": "time", "time_unit": "ms"}, "record_count", 3),
        "table.tsv": ("id\tvalue\na\t0\nb\t2\n", {}, "column_count", 2),
        "records.json": ('{"id":9007199254740993,"quantity":1.234567890123456789,"missing":null}', {}, "numeric_token_count", 2),
        "records.jsonl": ('{"x":1}\n\n{"x":2}\n', {}, "record_count", 2),
        "model.xml": ('<model unit="mm"><part id="a"/><part id="b"/></model>', {}, "element_count", 3),
        "ascii.stl": (triangle, {"length_unit": "mm"}, "face_count", 1),
        "binary.stl": (binary, {"length_unit": "m"}, "face_count", 1),
        "mesh.obj": ("v 0 0 0\nv 2 0 0\nv 0 3 0\nf 1 2 3\n", {"length_unit": "mm"}, "vertex_count", 3),
    }
    records = []
    for name, (value, options, metric, expected) in fixtures.items():
        source = inputs / name
        source.write_bytes(value if isinstance(value, bytes) else value.encode("utf-8"))
        bundle = args.output / name.replace(".", "-")
        execution = build(source, bundle, options={**DEFAULT_OPTIONS, **options})
        assert execution["checks_passed"], execution
        data = json.loads((bundle / "data/parsed.json").read_text())
        assert data["metrics"][metric] == expected
        if name.endswith((".stl", ".obj")):
            assert data["metrics"]["bbox"]["extent"] == [2.0, 3.0, 0.0]
        verified = verify_content(bundle, require_ready=True)
        records.append({"input": name, "bundle": bundle.relative_to(args.output).as_posix(),
                        "state": execution["state"], "independent_expected": {metric: expected},
                        "source_replay_validation": verified["source_replay_validation"],
                        "format_checks": verified["format_checks"]})
    report = {"inputs": len(records), "formats": 7, "results": records, "model_calls": 0, "backend_calls": 0,
              "scope": "Small synthetic fixtures; engineering acceptance concerns parsed data, not physical performance."}
    (args.output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
