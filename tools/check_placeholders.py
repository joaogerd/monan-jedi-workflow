#!/usr/bin/env python3
"""Inspect unresolved placeholders in MONAN-JEDI configuration templates.

This command-line utility searches files and directories for placeholder tokens
that still need to be rendered or intentionally documented before a workflow is
executed. It is mainly intended for the MONAN-JEDI configuration layer, where
YAML templates, environment examples, and shell fragments may contain values such
as ``{{ project_root }}`` or ``${MONAN_DATA_ROOT}``.

The check is intentionally conservative. A placeholder is not treated as a
runtime error by this tool, because some templates are expected to keep symbolic
values until a later rendering step. Instead, the script prints an inventory of
all detected placeholders so developers can review the provenance of each value.

Examples
--------
Inspect the default ``configs/`` directory::

    $ python tools/check_placeholders.py

Inspect a specific YAML file and a template directory::

    $ python tools/check_placeholders.py configs/sites/jaci.yaml templates/
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

# Match the two placeholder styles used by the workflow configuration layer:
#   1. Jinja-like placeholders: {{ variable_name }}
#   2. Shell-style placeholders: ${VARIABLE_NAME}
# The pattern deliberately avoids nested braces because nested placeholders are
# ambiguous in configuration files and should be handled explicitly upstream.
PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}|\$\{[^{}]+\}")


def scan_file(path: Path) -> list[str]:
    """Return all unique placeholders found in a text file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the file that will be scanned. The file is read as UTF-8 text.

    Returns
    -------
    list of str
        Sorted list containing each distinct placeholder token found in the
        file. The placeholders are returned exactly as they appear in the input
        text, including delimiters such as ``{{ ... }}`` or ``${...}``.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    UnicodeDecodeError
        If the file cannot be decoded as UTF-8 text.
    OSError
        If the file exists but cannot be read due to permissions or another
        operating-system error.

    Notes
    -----
    The function does not validate whether a placeholder is expected or valid
    for a specific template engine. It only performs lexical detection using the
    module-level regular expression ``PLACEHOLDER_RE``.

    See Also
    --------
    pathlib.Path.read_text : Read text data from a filesystem path.
    re.Pattern.findall : Find all non-overlapping regex matches.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("example.template")
    >>> _ = path.write_text("root={{ project_root }}\ninput=${MONAN_DATA_ROOT}\n", encoding="utf-8")
    >>> scan_file(path)
    ['${MONAN_DATA_ROOT}', '{{ project_root }}']
    >>> path.unlink()
    """
    text = path.read_text(encoding="utf-8")

    # Convert to a set to remove repeated tokens, then sort to make the output
    # stable across runs and easier to compare in logs or continuous integration.
    return sorted(set(PLACEHOLDER_RE.findall(text)))


def main() -> int:
    """Run the placeholder inspection command-line interface.

    Parameters
    ----------
    None
        Command-line arguments are read from ``sys.argv`` by ``argparse``.

    Returns
    -------
    int
        Process exit status. The function returns ``0`` even when placeholders
        are found, because the tool is an inspection utility rather than a
        strict validation gate.

    Raises
    ------
    OSError
        If one of the selected files cannot be accessed during scanning.
    UnicodeDecodeError
        If one of the selected files is not valid UTF-8 text.

    Notes
    -----
    Directory arguments are expanded recursively. Only files with suffixes that
    are relevant to the MONAN-JEDI configuration workflow are inspected:
    ``.yaml``, ``.yml``, ``.template``, ``.env``, and ``.example``.

    See Also
    --------
    scan_file : Return placeholders for a single file.
    argparse.ArgumentParser : Build command-line interfaces.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
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

        # Directories are searched recursively because site configurations often
        # spread templates across nested machine-, experiment-, and workflow-level
        # subdirectories.
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

        # Print one file block at a time so the output can be pasted directly
        # into documentation, issues, or provenance notes.
        any_placeholders = True
        print(f"{file_path}:")
        for item in placeholders:
            print(f"  - {item}")

    if not any_placeholders:
        print("No placeholders found.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
