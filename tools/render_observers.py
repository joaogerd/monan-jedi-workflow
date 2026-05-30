#!/usr/bin/env python3
"""Render and concatenate JEDI observer plug templates.

This tool assembles the JEDI ``observers`` YAML fragment from individual observer
plug templates declared in a manifest. It is a small and explicit replacement for
part of the upstream ``PrepJEDI.csh`` workflow behavior, where observation blocks
are selected, rendered, and inserted into the final variational application YAML.

The script does not validate the scientific correctness of any observer. It only
loads enabled observer entries, renders their templates with the shared context,
tracks unresolved placeholders, and writes a concatenated YAML fragment suitable
for insertion under ``cost function.observations.observers``.

Examples
--------
Render enabled observers with a context file::

    $ python tools/render_observers.py configs/experiments/3dvar_fgat/observers.yaml \
        --context configs/experiments/3dvar_fgat/render_context.yaml \
        --output build/rendered/observers.yaml

Preserve unresolved placeholders for template inspection::

    $ python tools/render_observers.py observers.yaml --context context.yaml \
        --output observers.rendered.yaml --allow-unresolved
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from render_template import load_context, render_text


def load_manifest(path: Path) -> list[dict[str, Any]]:
    """Load observer entries from a manifest YAML file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the observer manifest. The document must contain a top-level
        ``observers`` list.

    Returns
    -------
    list of dict
        Observer manifest entries. Each entry is expected to describe at least a
        template path and may include an ``enabled`` flag.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not exist.
    ValueError
        If the manifest does not contain a top-level ``observers`` key.
    TypeError
        If ``observers`` exists but is not a list.
    yaml.YAMLError
        If the file cannot be parsed as YAML.
    OSError
        If the file cannot be read.

    Notes
    -----
    The function validates only the manifest root. Individual entries are handled
    by ``main`` so disabled observers can be skipped before template rendering.

    See Also
    --------
    render_template.load_context : Load the YAML context used for rendering.
    render_template.render_text : Render each observer template.

    Examples
    --------
    >>> from pathlib import Path
    >>> path = Path("observers.yaml")
    >>> _ = path.write_text("observers:\n  - name: aircraft\n    template: aircraft.yaml\n", encoding="utf-8")
    >>> load_manifest(path)[0]["name"]
    'aircraft'
    >>> path.unlink()
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "observers" not in data:
        raise ValueError(f"Observer manifest must contain an 'observers' list: {path}")

    observers = data["observers"]
    if not isinstance(observers, list):
        raise TypeError("'observers' must be a list")

    return observers


def main() -> int:
    """Run the observer rendering command-line interface.

    Parameters
    ----------
    None
        Command-line arguments are parsed from ``sys.argv``.

    Returns
    -------
    int
        Exit status code. Returns ``0`` when all enabled observers are rendered
        successfully. Returns ``2`` when unresolved placeholders remain and
        ``--allow-unresolved`` was not selected.

    Raises
    ------
    FileNotFoundError
        If the manifest, context, or an enabled observer template does not exist.
    KeyError
        If an enabled manifest entry does not contain ``template``.
    yaml.YAMLError
        If the manifest or context cannot be parsed as YAML.
    OSError
        If input files cannot be read or the output file cannot be written.

    Notes
    -----
    Disabled entries, identified by ``enabled: false``, are skipped. Rendered
    fragments are stripped before concatenation to avoid accidental blank blocks
    between observer YAML sections.

    See Also
    --------
    load_manifest : Load the observer manifest.
    render_template.render_text : Render a template fragment.

    Examples
    --------
    >>> isinstance(main, object)
    True
    """
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

    # The output is a YAML list fragment. It intentionally does not add a parent
    # key because the fragment is later inserted into the JEDI application YAML.
    output_text = "\n".join(rendered_fragments).rstrip() + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(output_text, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
