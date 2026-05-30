#!/usr/bin/env python3
"""Check consistency across MONAN-JEDI input metadata files.

This utility compares three workflow metadata files used by the 3DVar-FGAT
input-provenance layer: the input source registry, the staging manifest, and the
scientific input checklist. The goal is to ensure that every declared input is
represented consistently across the files that describe where data come from,
how they are staged, and how they are scientifically audited.

The script performs structural and cross-reference checks only. It does not read
or validate the scientific content of the actual input files. It is intended to
run before staging or experiment execution so that metadata drift is detected
early and reported with explicit names.

Examples
--------
Check the default 3DVar-FGAT example metadata::

    $ python tools/check_input_consistency.py

Check explicit metadata files::

    $ python tools/check_input_consistency.py \
        --sources configs/experiments/3dvar_fgat/input_sources.yaml \
        --staging configs/experiments/3dvar_fgat/staging.yaml \
        --checklist configs/experiments/3dvar_fgat/scientific_input_checklist.yaml
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


def read_yaml(path: Path) -> Any:
    """Read a YAML document from a UTF-8 file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the YAML file to load.

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
        If the file cannot be read due to permissions or another filesystem
        problem.

    Notes
    -----
    The function intentionally does not validate schema details. Each metadata
    file has its own expected top-level key, checked by the command-line driver.

    See Also
    --------
    yaml.safe_load : Safely parse YAML documents.
    by_name : Convert validated lists into dictionaries indexed by ``name``.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("metadata.yaml")
    >>> _ = path.write_text("input_sources:\n  sources: []\n", encoding="utf-8")
    >>> read_yaml(path)["input_sources"]["sources"]
    []
    >>> path.unlink()
    """
    if not path.is_file():
        raise FileNotFoundError(str(path))

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def by_name(items: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    """Index metadata entries by their ``name`` field.

    Parameters
    ----------
    items : list of dict
        List of metadata entries. Each entry must contain a non-empty string
        field named ``name``.
    label : str
        Human-readable label used in error messages, for example ``"source"``
        or ``"staging"``.

    Returns
    -------
    dict of str to dict
        Mapping from entry name to the full metadata entry.

    Raises
    ------
    ValueError
        If an entry is missing a valid ``name`` field or if two entries share the
        same name.

    Notes
    -----
    Converting lists to dictionaries makes the cross-file comparison explicit:
    the validator can compare set differences between source names, staging
    names, and checklist names before checking field-level consistency.

    See Also
    --------
    read_yaml : Load the YAML files whose entries are indexed by this function.

    Examples
    --------
    >>> by_name([{"name": "background", "kind": "mpas"}], "source")["background"]["kind"]
    'mpas'
    >>> by_name([{"name": "a"}], "source") == {"a": {"name": "a"}}
    True
    """
    result: dict[str, dict[str, Any]] = {}

    for item in items:
        name = item.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{label} entry missing valid name")
        if name in result:
            raise ValueError(f"duplicate {label} entry: {name}")

        result[name] = item

    return result


def main() -> int:
    """Run the input metadata consistency checker.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when all names and fields are consistent.
        Returns ``2`` when a required mapping is missing, an entry is duplicated,
        or a cross-file mismatch is detected.

    Raises
    ------
    FileNotFoundError
        If one of the selected YAML files does not exist.
    yaml.YAMLError
        If one of the selected YAML files is invalid.
    OSError
        If a selected file cannot be read.

    Notes
    -----
    The checker compares both membership and selected metadata fields. The source
    registry is treated as the authoritative list of inputs. The staging manifest
    and scientific checklist must contain the same names and compatible values
    for target paths, required flags, and input kinds.

    See Also
    --------
    read_yaml : Load metadata files.
    by_name : Build dictionaries used for cross-file comparison.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
    parser = argparse.ArgumentParser(
        description="Check consistency between MONAN/JEDI input configuration files."
    )
    parser.add_argument(
        "--sources",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/input_sources.example.yaml"),
    )
    parser.add_argument(
        "--staging",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/staging.example.yaml"),
    )
    parser.add_argument(
        "--checklist",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat/scientific_input_checklist.yaml"),
    )
    args = parser.parse_args()

    sources_doc = read_yaml(args.sources)
    staging_doc = read_yaml(args.staging)
    checklist_doc = read_yaml(args.checklist)

    sources_root = sources_doc.get("input_sources") if isinstance(sources_doc, dict) else None
    staging_root = staging_doc.get("input_staging") if isinstance(staging_doc, dict) else None
    checklist_root = (
        checklist_doc.get("scientific_input_checklist") if isinstance(checklist_doc, dict) else None
    )

    if not isinstance(sources_root, dict):
        print("[ERROR] sources file must contain input_sources mapping")
        return 2
    if not isinstance(staging_root, dict):
        print("[ERROR] staging file must contain input_staging mapping")
        return 2
    if not isinstance(checklist_root, dict):
        print("[ERROR] checklist file must contain scientific_input_checklist mapping")
        return 2

    try:
        sources = by_name(sources_root.get("sources", []), "source")
        staging = by_name(staging_root.get("files", []), "staging")
        checklist = by_name(checklist_root.get("inputs", []), "checklist")
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 2

    ok = True

    source_names = set(sources)
    staging_names = set(staging)
    checklist_names = set(checklist)

    # Membership checks come first because field-level comparisons only make
    # sense for entries that are present in all three metadata files.
    missing_in_staging = sorted(source_names - staging_names)
    missing_in_checklist = sorted(source_names - checklist_names)
    extra_in_staging = sorted(staging_names - source_names)
    extra_in_checklist = sorted(checklist_names - source_names)

    for name in missing_in_staging:
        print(f"[ERROR] Source missing from staging manifest: {name}")
        ok = False
    for name in missing_in_checklist:
        print(f"[ERROR] Source missing from scientific checklist: {name}")
        ok = False
    for name in extra_in_staging:
        print(f"[ERROR] Staging entry missing from source registry: {name}")
        ok = False
    for name in extra_in_checklist:
        print(f"[ERROR] Checklist entry missing from source registry: {name}")
        ok = False

    for name in sorted(source_names & staging_names & checklist_names):
        source = sources[name]
        stage = staging[name]
        check = checklist[name]

        source_external_target = source.get("external_target")
        source_staged_target = source.get("staged_target")
        staging_target = stage.get("target")
        checklist_target = check.get("target")

        if source_external_target != staging_target:
            print(
                f"[ERROR] external/staging target mismatch for {name}: "
                f"source external_target={source_external_target!r} staging target={staging_target!r}"
            )
            ok = False

        if source_staged_target != checklist_target:
            print(
                f"[ERROR] staged/checklist target mismatch for {name}: "
                f"source staged_target={source_staged_target!r} checklist target={checklist_target!r}"
            )
            ok = False

        if bool(source.get("required", True)) != bool(stage.get("required", True)):
            print(f"[ERROR] required flag mismatch between source and staging for {name}")
            ok = False

        if bool(source.get("required", True)) != bool(check.get("required", True)):
            print(f"[ERROR] required flag mismatch between source and checklist for {name}")
            ok = False

        if source.get("kind") != stage.get("kind"):
            print(f"[ERROR] kind mismatch between source and staging for {name}")
            ok = False

        if source.get("kind") != check.get("kind"):
            print(f"[ERROR] kind mismatch between source and checklist for {name}")
            ok = False

        # Emit a progress line for every shared entry. This is useful in long HPC
        # logs because the user can see exactly which logical input was checked.
        if ok:
            pass
        print(f"[INFO] Consistency checked: {name}")

    if not ok:
        return 2

    print("[INFO] Input source/staging/checklist consistency check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
