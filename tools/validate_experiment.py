#!/usr/bin/env python3
"""Validate the structural layout of a MONAN-JEDI experiment.

This validator performs lightweight checks on a MONAN-JEDI experiment directory
and its rendered products. It verifies that expected configuration files exist,
that they expose required top-level YAML sections, and that key rendered files
contain expected text markers.

The script is intentionally not a scientific validator and not a full JEDI schema
validator. Its purpose is to catch missing files, incomplete rendering, or obvious
layout regressions in the 3DVar-FGAT workflow before users launch an HPC job.

Examples
--------
Validate the default 3DVar-FGAT experiment structure::

    $ python tools/validate_experiment.py

Validate explicit experiment and rendered directories::

    $ python tools/validate_experiment.py \
        --experiment-dir configs/experiments/3dvar_fgat \
        --rendered-dir build/rendered
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


class ValidationError(RuntimeError):
    """Represent a structural validation failure.

    Parameters
    ----------
    *args : tuple
        Positional arguments forwarded to ``RuntimeError``.

    Returns
    -------
    ValidationError
        Exception instance used to signal expected validation failures.

    Raises
    ------
    None
        The class itself does not raise during construction beyond the base
        exception behavior.

    Notes
    -----
    A dedicated exception keeps validation failures separate from unexpected
    programming errors or low-level I/O exceptions.

    See Also
    --------
    RuntimeError : Base class used for this validation exception.

    Examples
    --------
    >>> isinstance(ValidationError("missing"), RuntimeError)
    True
    """


def load_yaml(path: Path) -> Any:
    """Load a YAML file and report missing files as validation errors.

    Parameters
    ----------
    path : pathlib.Path
        YAML file path to load.

    Returns
    -------
    Any
        Python object returned by ``yaml.safe_load``.

    Raises
    ------
    ValidationError
        If the YAML file is missing.
    yaml.YAMLError
        If the file cannot be parsed as YAML.
    UnicodeDecodeError
        If the file cannot be decoded as UTF-8.
    OSError
        If the file cannot be read.

    Notes
    -----
    Missing files are converted to ``ValidationError`` so the command-line driver
    can print concise validation messages and return status code ``2``.

    See Also
    --------
    require_mapping : Require the loaded YAML object to be a mapping.
    yaml.safe_load : Parse YAML safely.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("experiment.yaml")
    >>> _ = path.write_text("experiment: {}\n", encoding="utf-8")
    >>> sorted(load_yaml(path).keys())
    ['experiment']
    >>> path.unlink()
    """
    if not path.is_file():
        raise ValidationError(f"Missing YAML file: {path}")

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def require_mapping(data: Any, path: Path) -> dict[str, Any]:
    """Require YAML content to be a mapping.

    Parameters
    ----------
    data : Any
        YAML-derived object to validate.
    path : pathlib.Path
        Source path used in diagnostic messages.

    Returns
    -------
    dict of str to Any
        The validated mapping.

    Raises
    ------
    ValidationError
        If ``data`` is not a dictionary.

    Notes
    -----
    Experiment configuration files in this workflow are expected to use mapping
    roots. Lists or scalar roots usually indicate that the wrong file was passed.

    See Also
    --------
    load_yaml : Load YAML content before mapping validation.

    Examples
    --------
    >>> require_mapping({"experiment": {}}, Path("experiment.yaml"))
    {'experiment': {}}
    """
    if not isinstance(data, dict):
        raise ValidationError(f"YAML file must contain a mapping: {path}")

    return data


def check_top_key(path: Path, key: str) -> None:
    """Check that a YAML file contains a required top-level key.

    Parameters
    ----------
    path : pathlib.Path
        YAML file to inspect.
    key : str
        Required top-level key.

    Returns
    -------
    None
        The function prints a success message or raises ``ValidationError``.

    Raises
    ------
    ValidationError
        If the file is missing, is not a mapping, or does not contain ``key``.
    yaml.YAMLError
        If the file cannot be parsed as YAML.

    Notes
    -----
    This check validates structural presence only. It does not validate the
    contents of the section associated with ``key``.

    See Also
    --------
    load_yaml : Load the YAML file.
    require_mapping : Ensure the YAML root is a mapping.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("observers.yaml")
    >>> _ = path.write_text("observers: []\n", encoding="utf-8")
    >>> check_top_key(path, "observers")
    [INFO] observers.yaml: found top-level key 'observers'
    >>> path.unlink()
    """
    data = require_mapping(load_yaml(path), path)
    if key not in data:
        raise ValidationError(f"Missing top-level key '{key}' in {path}")

    print(f"[INFO] {path}: found top-level key '{key}'")


def check_file_contains(path: Path, needles: list[str]) -> None:
    """Check that a text file contains all required strings.

    Parameters
    ----------
    path : pathlib.Path
        Text file to inspect.
    needles : list of str
        Strings that must all be present in the file.

    Returns
    -------
    None
        The function prints a success message or raises ``ValidationError``.

    Raises
    ------
    ValidationError
        If the file is missing or if any required string is absent.
    UnicodeDecodeError
        If the file cannot be decoded as UTF-8.
    OSError
        If the file cannot be read.

    Notes
    -----
    String checks are deliberately simple. They are intended to detect obvious
    rendering regressions without requiring a complete schema-aware parser.

    See Also
    --------
    check_file_contains_any : Check alternatives where more than one valid token
        is accepted.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("rendered.yaml")
    >>> _ = path.write_text("cost type: 3D-Var\nobservers:\n", encoding="utf-8")
    >>> check_file_contains(path, ["cost type: 3D-Var", "observers:"])
    [INFO] rendered.yaml: content check passed
    >>> path.unlink()
    """
    if not path.is_file():
        raise ValidationError(f"Missing file: {path}")

    text = path.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            raise ValidationError(f"Missing expected text in {path}: {needle}")

    print(f"[INFO] {path}: content check passed")


def check_file_contains_any(path: Path, alternatives: list[str], label: str) -> None:
    """Check that a text file contains at least one accepted string.

    Parameters
    ----------
    path : pathlib.Path
        Text file to inspect.
    alternatives : list of str
        Accepted strings. At least one must be present.
    label : str
        Human-readable label used in error and success messages.

    Returns
    -------
    None
        The function prints a success message or raises ``ValidationError``.

    Raises
    ------
    ValidationError
        If the file is missing or none of the alternatives is present.
    UnicodeDecodeError
        If the file cannot be decoded as UTF-8.
    OSError
        If the file cannot be read.

    Notes
    -----
    Alternative checks are useful when a rendered command may contain either a
    resolved executable path or the symbolic environment-variable reference.

    See Also
    --------
    check_file_contains : Require all listed strings to be present.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("command.txt")
    >>> _ = path.write_text("${MPASJEDI_VARIATIONAL_EXE} 3dvar.yaml\n", encoding="utf-8")
    >>> check_file_contains_any(path, ["mpasjedi_variational", "MPASJEDI_VARIATIONAL_EXE"], "executable")
    [INFO] command.txt: found executable
    >>> path.unlink()
    """
    if not path.is_file():
        raise ValidationError(f"Missing file: {path}")

    text = path.read_text(encoding="utf-8")
    if not any(item in text for item in alternatives):
        joined = " OR ".join(alternatives)
        raise ValidationError(f"Missing expected {label} in {path}: {joined}")

    print(f"[INFO] {path}: found {label}")


def main() -> int:
    """Run the experiment structural validator.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when all structural checks pass and ``2``
        when a validation failure is detected.

    Raises
    ------
    yaml.YAMLError
        If one of the YAML files is malformed.
    OSError
        If files cannot be read.

    Notes
    -----
    The default paths target the 3DVar-FGAT experiment and ``build/rendered``
    output directory. These defaults make the tool suitable for quick regression
    checks after template rendering.

    See Also
    --------
    check_top_key : Validate expected YAML sections.
    check_file_contains : Validate required rendered text markers.
    check_file_contains_any : Validate alternative rendered text markers.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
    parser = argparse.ArgumentParser(description="Validate MONAN/JEDI experiment structure.")
    parser.add_argument(
        "--experiment-dir",
        type=Path,
        default=Path("configs/experiments/3dvar_fgat"),
        help="Experiment configuration directory.",
    )
    parser.add_argument(
        "--rendered-dir",
        type=Path,
        default=Path("build/rendered"),
        help="Rendered output directory.",
    )
    args = parser.parse_args()

    exp = args.experiment_dir
    rendered = args.rendered_dir

    checks = [
        (exp / "experiment.yaml", "experiment"),
        (exp / "observers.yaml", "observers"),
        (exp / "runtime_manifest.example.yaml", "runtime"),
        (exp / "run_command.example.yaml", "variational_run"),
        (exp / "pbs_job.example.yaml", "pbs"),
    ]

    try:
        for path, key in checks:
            check_top_key(path, key)

        check_file_contains(
            rendered / "3dvar_fgat.yaml",
            ["cost type: 3D-Var", "observers:", "aircraft", "sondes", "sfc"],
        )
        check_file_contains(
            rendered / "observers.yaml",
            ["name: aircraft", "name: sondes", "name: sfc"],
        )
        check_file_contains_any(
            rendered / "mpasjedi_variational.command",
            ["mpasjedi_variational", "MPASJEDI_VARIATIONAL_EXE"],
            "variational executable reference",
        )
        check_file_contains(
            rendered / "mpasjedi_variational.command",
            ["3dvar_fgat.yaml"],
        )
        check_file_contains(
            rendered / "3dvar_fgat.pbs",
            ["#PBS -N", "#PBS -l select=", "exec mpirun -np", "MPASJEDI_VARIATIONAL_EXE"],
        )
    except ValidationError as exc:
        print(f"[ERROR] {exc}")
        return 2

    print("[INFO] Experiment structural validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
