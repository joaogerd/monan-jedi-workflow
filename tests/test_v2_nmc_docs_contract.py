"""Documentation contract checks for the V2 NMC pair stage."""

from __future__ import annotations

import inspect
from pathlib import Path

from monan_jedi_workflow.components.bmatrix.nmc_pairs.config import NmcPairsSettings
from monan_jedi_workflow.components.bmatrix.nmc_pairs.manifest import BflowManifest, read_bflow_manifest, write_bflow_manifest
from monan_jedi_workflow.components.bmatrix.nmc_pairs.model import NmcForecast, NmcPair, normalize_time, plan_pairs
from monan_jedi_workflow.components.bmatrix.nmc_pairs.stage import NmcPairsStage
from monan_jedi_workflow.components.bmatrix.nmc_pairs.validation import validate_bflow_manifest, validate_pairs
from monan_jedi_workflow.components.model.mpas.products import MpasForecastProductLayout


def test_nmc_public_api_has_docstrings() -> None:
    """Public NMC API objects must retain non-empty documentation."""
    public = (
        NmcPairsSettings,
        BflowManifest,
        NmcForecast,
        NmcPair,
        NmcPairsStage,
        MpasForecastProductLayout,
        normalize_time,
        plan_pairs,
        read_bflow_manifest,
        write_bflow_manifest,
        validate_pairs,
        validate_bflow_manifest,
    )
    assert all(inspect.getdoc(item) for item in public)


def test_nmc_tool_page_contains_required_sections() -> None:
    """The NMC Markdown page must retain the project documentation sections."""
    page = Path("docs/tools/bmatrix/nmc-pairs.md").read_text(encoding="utf-8")
    required = (
        "## Purpose",
        "## Inputs",
        "## Outputs",
        "## Artifact Contract",
        "## YAML Configuration",
        "## Parameters",
        "## Dependencies",
        "## CLI Usage",
        "## Validation and Restart Behavior",
        "## Limitations",
        "## FAQ",
        "## References",
    )
    assert all(section in page for section in required)
