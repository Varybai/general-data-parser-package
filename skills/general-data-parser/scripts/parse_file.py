#!/usr/bin/env python3
"""Parse an engineering file and execute the declared acceptance checks."""

import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

import engineering_adapters as adapters
from engineering_runtime import DEFAULT_OPTIONS, build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--format", choices=sorted(adapters.FORMATS))
    parser.add_argument("--list-formats", action="store_true")
    parser.add_argument("--object-id")
    parser.add_argument("--version", default="v1")
    parser.add_argument("--encoding", default=DEFAULT_OPTIONS["encoding"])
    parser.add_argument("--no-header", action="store_true")
    parser.add_argument("--time-column")
    parser.add_argument("--time-unit", choices=["s", "ms", "us", "ns"])
    parser.add_argument("--time-order", choices=["strict", "nondecreasing"], default="strict")
    parser.add_argument("--length-unit", choices=["m", "cm", "mm", "in", "ft"])
    parser.add_argument("--require-unit", action="store_true")
    parser.add_argument("--require-observation", action="store_true")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_OPTIONS["max_bytes"])
    parser.add_argument("--max-items", type=int, default=DEFAULT_OPTIONS["max_items"])
    parser.add_argument("--abs-tolerance", type=float, default=DEFAULT_OPTIONS["abs_tolerance"])
    parser.add_argument("--rel-tolerance", type=float, default=DEFAULT_OPTIONS["rel_tolerance"])
    args = parser.parse_args()
    if args.list_formats:
        print(json.dumps(adapters.FORMATS, ensure_ascii=False, indent=2))
        return 0
    if not args.source or not args.output:
        parser.error("source and --output are required")
    options = {key: getattr(args, key) for key in DEFAULT_OPTIONS if key != "header"}
    options["header"] = not args.no_header
    try:
        result = build(args.source, args.output, args.format, options, args.object_id, args.version)
    except (ValueError, OSError, RecursionError) as exc:
        print(json.dumps({"state": "unsupported" if isinstance(exc, adapters.Unsupported) else "failed",
                          "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["checks_passed"] else 2


if __name__ == "__main__":
    sys.exit(main())
