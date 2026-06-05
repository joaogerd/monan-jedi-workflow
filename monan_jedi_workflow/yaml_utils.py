"""YAML loading helpers for MONAN-JEDI workflow configuration.

This module contains small, strict utilities for reading YAML configuration
files used by the workflow. The helpers intentionally validate the top-level
shape of each file so later configuration code can operate on mappings safely.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Load a YAML file and require a mapping at the top level.

    Parameters
    ----------
    path : pathlib.Path
        Path to the YAML file to read.

    Returns
    -------
    dict[str, typing.Any]
        Parsed YAML mapping. Empty YAML files are normalized to an empty
        dictionary.

    Raises
    ------
    FileNotFoundError
        If ``path`` does not point to an existing regular file.
    yaml.YAMLError
        If the file contains invalid YAML syntax.
    TypeError
        If the parsed YAML document is not a mapping.

    Notes
    -----
    The workflow stores experiment configuration in several YAML files. This
    helper enforces a common top-level contract for all of them: each file must
    parse to a dictionary. That avoids obscure errors later when validation or
    rendering code expects mapping-style access.

    See Also
    --------
    monan_jedi_workflow.config.load_experiment_config : Load all split
        configuration files for an experiment.

    Examples
    --------
    >>> from pathlib import Path
    >>> import tempfile
    >>> with tempfile.TemporaryDirectory() as tmp:
    ...     path = Path(tmp) / "config.yaml"
    ...     _ = path.write_text("experiment:\\n  name: demo\\n", encoding="utf-8")
    ...     load_yaml_file(path)["experiment"]["name"]
    'demo'
    """
    if not path.is_file():
        raise FileNotFoundError(f"YAML file not found: {path}")

    # Use safe_load because these files are declarative configuration, not a
    # place where arbitrary Python objects should be constructed.
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)

    # Empty YAML files are valid from a parser perspective. Normalizing them to
    # an empty mapping gives callers a predictable return type.
    if data is None:
        return {}

    if not isinstance(data, dict):
        raise TypeError(f"YAML file must contain a top-level mapping: {path}")

    return data
