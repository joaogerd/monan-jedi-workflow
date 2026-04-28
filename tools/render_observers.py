#!/usr/bin/env python3
"""Render and concatenate JEDI observer plug templates.

This tool is a small, explicit replacement for the first part of the upstream PrepJEDI.csh
behavior: assembling the `observers` section from individual observation plug templates.

It does not validate the scientific correctness of any observer. It only renders selected plug
files and concatenates them into a YAML list suitable for insertion under:

  cost function:
    observations:
      observers:

The resulting file can then be included in the render context for the JEDI application template.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from render_template import load_context, render_text


def load_manifest(path: Path) -> list[dict[str, Any]]:
    """Load observer manifest entries."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "observers" not in data:
        raise ValueError(f"Observer manifest must contain an 'observers' list: {path}")
    observers = data["observers"]
    if not isinstance(observers, list):
        raise TypeError("'observers' must be a list")
    return observers


def main() -> int:
    parser = argparse.ArgumentParser(description="Render JEDI observer plug templates.")
    parser.add_argument("manifest", type=Path, help="Observer manifest YAML")
    parser.add_argument("--context", type=Path, required=True, help="YAML rendering context")
    parser.add_argument("--output", type=Path, required=True, help="Output observers YAML fragment")
    parser.add_argument("--allow-env", action="store_true", help="Allow {{name}} lookup from environment")
    parser.add_argument("--allow-unresolved", action="store_true", help="Preserve unresolved placeholders")
    args = parser.parse_args()

    context = load_context(args.context)
    rendered_fragments: list[str] = []
    unresolved_all: list[str] = []

    for entry in load_manifest(args.manifest):
        if not entry.get("enabled", True):
            continue
        template = Path(entry["template"])
        if not template.is_file():
            raise FileNotFoundError(f"Observer template not found: {template}")
        text = template.read_text(encoding="utf-8")
        rendered, unresolved = render_text(
            text,
            context,
            allow_env=args.allow_env,
            allow_unresolved=args.allow_unresolved,
        )
        unresolved_all.extend(unresolved)
        rendered_fragments.append(rendered.strip())

    if unresolved_all and not args.allow_unresolved:
        print("[ERROR] Unresolved observer placeholders:")
        for item in sorted(set(unresolved_all)):
            print(f"  - {item}")
        return 2

    output_text = "\n".join(rendered_fragments).rstrip() + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output_text, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
