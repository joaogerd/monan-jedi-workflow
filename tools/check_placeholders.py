#!/usr/bin/env python3
"""Inspect MONAN/JEDI template placeholders.

This utility scans selected configuration templates and reports unresolved placeholder tokens.
It is intentionally conservative: placeholders are allowed in scientific templates, but they
must remain visible and documented until the template rendering layer is implemented.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}|\$\{[^{}]+\}")


def scan_file(path: Path) -> list[str]:
    """Return sorted unique placeholders found in *path*."""
    text = path.read_text(encoding="utf-8")
    return sorted(set(PLACEHOLDER_RE.findall(text)))


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect unresolved template placeholders.")
    parser.add_argument(
        "paths",
        nargs="*",
        default=["configs"],
        help="Files or directories to inspect. Defaults to configs/.",
    )
    args = parser.parse_args()

    files: list[Path] = []
    for raw in args.paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(
                p for p in path.rglob("*")
                if p.is_file() and p.suffix in {".yaml", ".yml", ".template", ".env", ".example"}
            )
        elif path.is_file():
            files.append(path)

    any_placeholders = False
    for file_path in sorted(files):
        placeholders = scan_file(file_path)
        if not placeholders:
            continue
        any_placeholders = True
        print(f"{file_path}:")
        for item in placeholders:
            print(f"  - {item}")

    if not any_placeholders:
        print("No placeholders found.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
