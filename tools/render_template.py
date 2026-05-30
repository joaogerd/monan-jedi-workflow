#!/usr/bin/env python3
"""Render MONAN-JEDI workflow text templates.

The original NCAR/MPAS workflow uses task scripts to generate many runtime files
through shell-level string substitution. This module provides a small, explicit,
and testable renderer for the MONAN-JEDI workflow. It replaces placeholders in
text templates using values from a YAML context file and, when requested, from
the process environment.

Supported placeholder styles are ``{{name}}`` and ``${NAME}``. The double-brace
syntax is primarily intended for YAML context values, including nested keys such
as ``{{experiment.name}}`` or ``{{cycle.window.begin}}``. The environment syntax
is primarily intended for shell variables such as ``${MONAN_DATA_ROOT}``.

The renderer is strict by default. Unresolved placeholders cause a non-zero exit
status unless ``--allow-unresolved`` is used. This behavior is useful in HPC
workflows because a rendered file with unresolved paths can waste queue time or
produce difficult-to-debug JEDI failures.

Examples
--------
Render a template to standard output::

    $ python tools/render_template.py templates/3dvar_fgat.yaml.template -c context.yaml

Render a template to a file and allow unresolved placeholders for inspection::

    $ python tools/render_template.py input.template -c context.yaml -o build/rendered/input.yaml --allow-unresolved
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - runtime dependency check
    raise SystemExit("PyYAML is required: pip install pyyaml") from exc

# Match {{ key }} placeholders. The captured key may use dot notation to access
# nested YAML dictionaries.
DOUBLE_BRACE_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")

# Match ${NAME} placeholders using a conservative shell-variable name pattern.
ENV_RE = re.compile(r"\$\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}")


def load_context(path: Path | None) -> dict[str, Any]:
    """Load a YAML rendering context.

    Parameters
    ----------
    path : pathlib.Path or None
        YAML file containing replacement values. If ``None``, an empty context
        is returned.

    Returns
    -------
    dict of str to Any
        Parsed context dictionary. Empty YAML files also produce an empty
        dictionary.

    Raises
    ------
    FileNotFoundError
        If ``path`` is provided but does not point to an existing file.
    TypeError
        If the YAML document root is not a mapping.
    yaml.YAMLError
        If the YAML file cannot be parsed.
    UnicodeDecodeError
        If the file cannot be decoded as UTF-8.
    OSError
        If the file cannot be read.

    Notes
    -----
    The renderer expects a mapping because placeholders are resolved by key. A
    list or scalar context would make dot-notation lookup ambiguous.

    See Also
    --------
    lookup : Resolve dot-notation keys from the loaded context.
    yaml.safe_load : Parse YAML into standard Python objects.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("context.yaml")
    >>> _ = path.write_text("experiment:\n  name: test\n", encoding="utf-8")
    >>> load_context(path)["experiment"]["name"]
    'test'
    >>> path.unlink()
    >>> load_context(None)
    {}
    """
    if path is None:
        return {}
    if not path.is_file():
        raise FileNotFoundError(f"Context file not found: {path}")

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise TypeError(f"Context file must contain a YAML mapping: {path}")

    return data


def lookup(context: dict[str, Any], key: str) -> Any:
    """Resolve a dot-notation key against a nested dictionary.

    Parameters
    ----------
    context : dict of str to Any
        Rendering context loaded from YAML.
    key : str
        Key to resolve. Dots indicate nested dictionary access, for example
        ``"experiment.name"``.

    Returns
    -------
    Any
        Value stored in the context for the requested key.

    Raises
    ------
    KeyError
        If any key component is missing or if traversal reaches a non-dictionary
        value before the final component.

    Notes
    -----
    The function performs exact key matching after stripping whitespace around
    each dot-separated component. It does not evaluate expressions.

    See Also
    --------
    stringify : Convert resolved values into template-safe strings.

    Examples
    --------
    >>> lookup({"experiment": {"name": "3dvar"}}, "experiment.name")
    '3dvar'
    """
    current: Any = context
    for part in key.split("."):
        part = part.strip()
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise KeyError(key)

    return current


def stringify(value: Any) -> str:
    """Convert a YAML value to a string suitable for template substitution.

    Parameters
    ----------
    value : Any
        Value resolved from the YAML context or environment.

    Returns
    -------
    str
        Textual representation used in the rendered output.

    Raises
    ------
    None
        The function relies on ``str`` for generic values and does not raise for
        normal Python objects.

    Notes
    -----
    Boolean values are rendered as lowercase ``true`` and ``false`` because many
    YAML and shell fragments expect lowercase logical values. Lists and tuples
    are rendered as comma-separated values for compact template insertion.

    See Also
    --------
    render_text : Apply ``stringify`` during placeholder replacement.

    Examples
    --------
    >>> stringify(True)
    'true'
    >>> stringify(["a", "b"])
    'a, b'
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    if value is None:
        return "None"

    return str(value)


def render_text(
    text: str,
    context: dict[str, Any],
    *,
    allow_env: bool,
    allow_unresolved: bool,
) -> tuple[str, list[str]]:
    """Render template text using a YAML context and optional environment values.

    Parameters
    ----------
    text : str
        Template text containing ``{{...}}`` and/or ``${...}`` placeholders.
    context : dict of str to Any
        YAML-derived replacement values.
    allow_env : bool
        If ``True``, unresolved ``{{...}}`` placeholders may be filled from the
        process environment. ``${...}`` placeholders always check the
        environment after the YAML context.
    allow_unresolved : bool
        If ``True``, unresolved placeholders are preserved in the rendered text
        and reported to the caller. If ``False``, they are also preserved but are
        intended to make the command-line driver fail.

    Returns
    -------
    tuple of str and list of str
        Rendered text and a sorted list of unique unresolved placeholders.

    Raises
    ------
    re.error
        If the module-level regular expressions are invalid. This should not
        occur during normal execution.

    Notes
    -----
    The YAML context takes precedence over environment variables for both
    placeholder styles. This makes rendered workflow files reproducible from a
    context document while still allowing selected environment-driven values.

    See Also
    --------
    lookup : Resolve keys from the context.
    stringify : Convert resolved values to text.

    Examples
    --------
    >>> render_text("name={{experiment.name}}", {"experiment": {"name": "fgat"}}, allow_env=False, allow_unresolved=False)
    ('name=fgat', [])
    >>> render_text("root=${MISSING_ROOT}", {}, allow_env=False, allow_unresolved=True)[1]
    ['${MISSING_ROOT}']
    """
    unresolved: list[str] = []

    def replace_double(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        try:
            return stringify(lookup(context, key))
        except KeyError:
            if allow_env and key in os.environ:
                return os.environ[key]
            unresolved.append(f"{{{{{key}}}}}")
            return match.group(0) if allow_unresolved else match.group(0)

    def replace_env(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        try:
            return stringify(lookup(context, key))
        except KeyError:
            if key in os.environ:
                return os.environ[key]
            unresolved.append(f"${{{key}}}")
            return match.group(0) if allow_unresolved else match.group(0)

    rendered = DOUBLE_BRACE_RE.sub(replace_double, text)
    rendered = ENV_RE.sub(replace_env, rendered)

    # Remove duplicates and sort unresolved placeholders for deterministic logs.
    return rendered, sorted(set(unresolved))


def main() -> int:
    """Run the template renderer command-line interface.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when rendering succeeds or unresolved
        placeholders are explicitly allowed. Returns ``2`` when unresolved
        placeholders remain in strict mode.

    Raises
    ------
    FileNotFoundError
        If the template or context file does not exist.
    TypeError
        If the context file is not a YAML mapping.
    yaml.YAMLError
        If the context file cannot be parsed.
    OSError
        If files cannot be read or written.

    Notes
    -----
    Parent directories for ``--output`` are created automatically. Without
    ``--output``, rendered text is written to standard output so the tool can be
    used inside shell pipelines.

    See Also
    --------
    load_context : Load YAML replacement values.
    render_text : Render the template body.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
    parser = argparse.ArgumentParser(description="Render a MONAN-JEDI-WORKFLOW template.")
    parser.add_argument("template", type=Path, help="Input template file")
    parser.add_argument("-c", "--context", type=Path, help="YAML context file")
    parser.add_argument("-o", "--output", type=Path, help="Output file. Defaults to stdout.")
    parser.add_argument("--allow-env", action="store_true", help="Allow {{name}} lookup from environment")
    parser.add_argument(
        "--allow-unresolved",
        action="store_true",
        help="Write output even if placeholders remain unresolved",
    )
    args = parser.parse_args()

    context = load_context(args.context)
    text = args.template.read_text(encoding="utf-8")
    rendered, unresolved = render_text(
        text,
        context,
        allow_env=args.allow_env,
        allow_unresolved=args.allow_unresolved,
    )

    if unresolved and not args.allow_unresolved:
        print("[ERROR] Unresolved placeholders:", file=sys.stderr)
        for item in unresolved:
            print(f"  - {item}", file=sys.stderr)
        return 2

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    if unresolved:
        print("[WARN] Unresolved placeholders were preserved:", file=sys.stderr)
        for item in unresolved:
            print(f"  - {item}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
