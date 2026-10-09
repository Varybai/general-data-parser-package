#!/usr/bin/env python3
"""Re-read the bound source using a registered adapter; verify actual content."""

import argparse
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True

from engineering_runtime import verify_content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    try:
        result = verify_content(args.bundle, args.require_ready)
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        print(json.dumps({"source_replay_validation": "fail", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
