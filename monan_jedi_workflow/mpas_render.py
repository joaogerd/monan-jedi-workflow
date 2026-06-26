"""Declarative rendering helpers for cycle-specific MPAS runtime files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .stage_config import StageConfigurationError, render_text


def patch_namelist(path: Path, replacements: dict[str, Any], context: dict[str, str]) -> None:
    """Replace existing Fortran namelist scalar values by configured keys."""
    if not path.is_file():
        raise FileNotFoundError(f"MPAS namelist does not exist: {path}")
    if not isinstance(replacements, dict):
        raise StageConfigurationError("mpas.namelist_replacements must be a mapping.")

    text = path.read_text(encoding="utf-8")
    for key, raw_value in replacements.items():
        if not isinstance(key, str) or not key:
            raise StageConfigurationError("mpas.namelist_replacements keys must be non-empty strings.")
        value = render_text(raw_value, context, label=f"mpas.namelist_replacements.{key}")
        pattern = re.compile(rf"^(\\s*{re.escape(key)}\\s*=\\s*)[^,\\n]*(.*)$", re.MULTILINE)
        text, count = pattern.subn(rf"\\g<1>{value}\\g<2>", text)
        if count != 1:
            raise StageConfigurationError(
                f"MPAS namelist replacement expected exactly one {key!r} entry, found {count}."
            )
    path.write_text(text, encoding="utf-8")


def patch_streams(path: Path, overrides: list[Any], context: dict[str, str]) -> None:
    """Set declared attributes on named MPAS stream XML elements."""
    if not path.is_file():
        raise FileNotFoundError(f"MPAS streams file does not exist: {path}")
    if not isinstance(overrides, list):
        raise StageConfigurationError("mpas.stream_overrides must be a list.")

    tree = ElementTree.parse(path)
    root = tree.getroot()
    for index, raw_item in enumerate(overrides):
        if not isinstance(raw_item, dict):
            raise StageConfigurationError(f"mpas.stream_overrides[{index}] must be a mapping.")
        name = raw_item.get("name")
        if not isinstance(name, str) or not name:
            raise StageConfigurationError(f"mpas.stream_overrides[{index}].name must be a non-empty string.")
        attributes = raw_item.get("attributes")
        if not isinstance(attributes, dict) or not attributes:
            raise StageConfigurationError(
                f"mpas.stream_overrides[{index}].attributes must be a non-empty mapping."
            )
        matches = [child for child in root if child.get("name") == name]
        if len(matches) != 1:
            raise StageConfigurationError(
                f"MPAS streams override expected exactly one stream named {name!r}, found {len(matches)}."
            )
        stream = matches[0]
        for attribute, raw_value in attributes.items():
            if not isinstance(attribute, str) or not attribute:
                raise StageConfigurationError(
                    f"mpas.stream_overrides[{index}].attributes keys must be non-empty strings."
                )
            stream.set(
                attribute,
                render_text(
                    raw_value,
                    context,
                    label=f"mpas.stream_overrides[{index}].attributes.{attribute}",
                ),
            )
    tree.write(path, encoding="unicode")
