#!/usr/bin/env python3
"""Check consistency of a MONAN-JEDI observer manifest.

This utility validates the observer manifest used by a MONAN-JEDI experiment. It
checks that the manifest contains an ``observers`` list, that each observer entry
has a unique name, a valid template path, a boolean ``enabled`` flag, and that the
observer name appears inside the referenced template.

The check is structural only. It does not validate the complete JEDI/UFO observer
schema, the scientific correctness of filters, or the availability of the IODA
files referenced by rendered observer blocks.

Examples
--------
Check the default 3DVar-FGAT observer manifest::

    $ python tools/check_observer_manifest.py

Check an explicit manifest::

    $ python tools/check_observer_manifest.py configs/experiments/3dvar_fgat/observers.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def main() -> int:
    """Run the observer manifest consistency checker.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when all observer entries pass the
        structural checks and ``2`` when the manifest is missing, malformed, or
        inconsistent.

    Raises
    ------
    yaml.YAMLError
        If the manifest cannot be parsed as YAML.
    UnicodeDecodeError
        If the manifest or template files cannot be decoded as UTF-8.
    OSError
        If the manifest or template files cannot be read.

    Notes
    -----
    The template-name check is intentionally simple. It catches common mistakes
    where a manifest entry points to the wrong observer plug template, without
    requiring a full YAML schema validator.

    See Also
    --------
    pathlib.Path.is_file : Check whether manifest and template paths exist.
    yaml.safe_load : Parse the manifest YAML document.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
    parser = argparse.ArgumentParser(description="Check observer manifest consistency.")
    parser.add_argument(
        "manifest",
        nargs="?",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/observers.yaml"),
    )
    args = parser.parse_args()

    if not args.manifest.is_file():
        print(f"[ERROR] Missing manifest: {args.manifest}")
        return 2

    data = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("observers"), list):
        print("[ERROR] Manifest must contain an observers list")
        return 2

    seen = set()
    for entry in data["observers"]:
        if not isinstance(entry, dict):
            print("[ERROR] Each observer entry must be a mapping")
            return 2

        name = entry.get("name")
        template = entry.get("template")
        enabled = entry.get("enabled")
        if not isinstance(name, str) or not name:
            print("[ERROR] Invalid observer name")
            return 2
        if name in seen:
            print(f"[ERROR] Duplicate observer name: {name}")
            return 2
        seen.add(name)

        if not isinstance(template, str) or not template:
            print(f"[ERROR] Invalid template for observer: {name}")
            return 2
        if not isinstance(enabled, bool):
            print(f"[ERROR] Invalid enabled flag for observer: {name}")
            return 2

        template_path = Path(template)
        if not template_path.is_file():
            print(f"[ERROR] Missing template for observer {name}: {template_path}")
            return 2

        text = template_path.read_text(encoding="utf-8")
        if name not in text:
            print(f"[ERROR] Observer name not found in template {template_path}: {name}")
            return 2

        print(f"[INFO] Observer entry validated: {name}")

    print("[INFO] Observer manifest check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
