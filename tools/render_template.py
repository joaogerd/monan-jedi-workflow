#!/usr/bin/env python3
"""Render MONAN-JEDI-WORKFLOW text templates.

The original NCAR/MPAS-Workflow relies heavily on C-shell-generated files and string
substitution performed inside task scripts such as PrepJEDI.csh. This tool provides a small,
explicit and testable replacement layer for the MONAN workflow.

Supported placeholders
----------------------

Two placeholder styles are supported:

- ``{{name}}``: value must come from a YAML context file, unless ``--allow-env`` is used.
- ``${NAME}``: value comes from the environment, unless provided by the YAML context.

Nested YAML values may be addressed with dot notation, for example:

- ``{{experiment.name}}``
- ``{{cycle.window.begin}}``
- ``{{paths.background_dir}}``

The renderer is intentionally strict by default: unresolved placeholders cause a non-zero exit.
Use ``--allow-unresolved`` only for documentation or partial-template inspection.
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

DOUBLE_BRACE_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
ENV_RE = re.compile(r"\$\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}")


def load_context(path: Path | None) -> dict[str, Any]:
    """Load a YAML context file.

    Parameters
    ----------
    path : pathlib.Path or None
        YAML file with replacement values.

    Returns
    -------
    dict
        Parsed context dictionary. Empty when ``path`` is None.
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
    """Resolve ``key`` using dot notation against ``context``."""
    current: Any = context
    for part in key.split("."):
        part = part.strip()
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            raise KeyError(key)
    return current


def stringify(value: Any) -> str:
    """Convert a YAML value to a template-safe string."""
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
    """Render template text and return unresolved placeholder names."""
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
    return rendered, sorted(set(unresolved))


def main() -> int:
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
