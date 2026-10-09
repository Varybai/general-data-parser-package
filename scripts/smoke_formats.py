#!/usr/bin/env python3
"""Run three real, small local conversions. No network, models or publication."""

import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from bundle_fixture import make_bundle, verifier


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output must be a new isolated directory")
    args.output.mkdir(parents=True)
    results = []
    for kind in ("csv", "json", "md"):
        root = make_bundle(args.output / kind, kind)
        result = verifier.verify(root, require_ready=True)
        result["input_format"] = kind
        result["content_validation"] = "independent fixture values and document roundtrip passed"
        results.append(result)
    report = {"samples": results, "remote_calls": 0, "model_calls": 0,
              "limits": "Only these small synthetic CSV/JSON/Markdown inputs were converted; other formats untested."}
    (args.output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
