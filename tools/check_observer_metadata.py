#!/usr/bin/env python3
"""Check observer metadata coverage for an experiment manifest.

This utility compares the experiment observer manifest against the observer plug
metadata registry. It verifies that every observer declared in the experiment has
metadata, that required metadata keys are present, and that the template path in
the metadata registry matches the template path declared by the experiment.

The check supports provenance and documentation of observer configuration. It is
not a full UFO/JEDI schema validator and does not inspect the rendered observer
YAML or IODA file contents.

Examples
--------
Check metadata coverage for the default 3DVar-FGAT observer manifest::

    $ python tools/check_observer_metadata.py

Use explicit manifest and metadata registry files::

    $ python tools/check_observer_metadata.py \
        --manifest configs/experiments/3dvar_fgat/observers.yaml \
        --metadata configs/jedi/obs_plugs/variational/metadata.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


def read_yaml(path: Path) -> Any:
    """Read a YAML document from disk.

    Parameters
    ----------
    path : pathlib.Path
        YAML file path to load as UTF-8 text.

    Returns
    -------
    Any
        Python object returned by ``yaml.safe_load``.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist or is not a regular file.
    yaml.YAMLError
        If the file cannot be parsed as YAML.
    UnicodeDecodeError
        If the file cannot be decoded as UTF-8.
    OSError
        If the file cannot be read.

    Notes
    -----
    The function performs generic YAML loading only. The expected top-level
    structures are checked by ``main``.

    See Also
    --------
    yaml.safe_load : Parse YAML into standard Python objects.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("metadata.yaml")
    >>> _ = path.write_text("observer_plugs: {}\n", encoding="utf-8")
    >>> read_yaml(path)["observer_plugs"]
    {}
    >>> path.unlink()
    """
    if not path.is_file():
        raise FileNotFoundError(str(path))

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def main() -> int:
    """Run the observer metadata coverage checker.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when metadata coverage is complete and
        ``2`` when required metadata is missing or inconsistent.

    Raises
    ------
    FileNotFoundError
        If the observer manifest or metadata file does not exist.
    yaml.YAMLError
        If one of the YAML files cannot be parsed.
    OSError
        If one of the files cannot be read.

    Notes
    -----
    Required metadata keys include provenance and operational fields such as
    ``status``, ``category``, ``expected_ioda_group``, ``validated_on_jaci``, and
    ``notes``. These fields help document which observer plugs are mature enough
    for workflow use.

    See Also
    --------
    read_yaml : Load the manifest and metadata registry.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
    parser = argparse.ArgumentParser(description="Check observer metadata coverage.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/observers.yaml"),
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("configs/jedi/obs_plugs/variational/metadata.yaml"),
    )
    args = parser.parse_args()

    manifest = read_yaml(args.manifest)
    metadata = read_yaml(args.metadata)

    observers = manifest.get("observers") if isinstance(manifest, dict) else None
    registry = metadata.get("observer_plugs") if isinstance(metadata, dict) else None

    if not isinstance(observers, list):
        print("[ERROR] Manifest does not contain an observers list")
        return 2
    if not isinstance(registry, dict):
        print("[ERROR] Metadata does not contain observer_plugs mapping")
        return 2

    required_keys = {
        "template",
        "status",
        "category",
        "expected_ioda_group",
        "requires_bias_correction",
        "validated_on_jaci",
        "notes",
    }

    ok = True
    for entry in observers:
        name = entry.get("name") if isinstance(entry, dict) else None
        if not isinstance(name, str):
            print("[ERROR] Invalid observer entry in manifest")
            ok = False
            continue

        item = registry.get(name)
        if not isinstance(item, dict):
            print(f"[ERROR] Missing metadata for observer: {name}")
            ok = False
            continue

        missing = sorted(required_keys - set(item.keys()))
        if missing:
            print(f"[ERROR] Metadata for {name} is missing keys: {', '.join(missing)}")
            ok = False
            continue

        if item["template"] != entry.get("template"):
            print(f"[ERROR] Template mismatch for {name}")
            ok = False
            continue

        print(
            f"[INFO] Observer metadata: {name} "
            f"status={item['status']} category={item['category']} "
            f"validated_on_jaci={item['validated_on_jaci']}"
        )

    if not ok:
        return 2

    print("[INFO] Observer metadata coverage check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
