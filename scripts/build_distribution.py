#!/usr/bin/env python3
"""Build a deterministic ZIP containing only the portable Skill directory."""

import hashlib
import json
from pathlib import Path
import zipfile

from check_package import check


def main():
    package = Path(__file__).resolve().parents[1]
    skill = package / "skills" / "general-data-parser"
    check(skill)
    target = package / "dist"
    target.mkdir(exist_ok=True)
    archive = target / "general-data-parser-0.1.0.zip"
    paths = sorted(path for path in skill.rglob("*") if path.is_file())
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for path in paths:
            name = "general-data-parser/" + path.relative_to(skill).as_posix()
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 9, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(info, path.read_bytes())
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    (target / "checksums.sha256").write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    print(json.dumps({"archive": str(archive), "files": len(paths), "sha256": checksum}, indent=2))


if __name__ == "__main__":
    main()
