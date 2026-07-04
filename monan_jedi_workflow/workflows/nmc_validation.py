"""Audit existing V2 NMC campaign artifacts without submitting work."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.stage import RunContext
from ..core.validation import ValidationReport
from .nmc_campaign import NmcCampaignPlan


@dataclass(frozen=True)
class NmcCampaignValidation:
    """Structured audit result for one existing NMC campaign workspace.

    Parameters
    ----------
    reports : dict[str, ValidationReport]
        Output-validation report for each stage keyed by stage identifier.
    """

    reports: dict[str, ValidationReport]

    @property
    def is_valid(self) -> bool:
        """Return whether every stage output contract currently validates."""
        return all(report.is_valid for report in self.reports.values())

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON representation of the campaign audit."""
        return {
            "is_valid": self.is_valid,
            "stages": {name: report.to_dict() for name, report in self.reports.items()},
        }


def validate_nmc_campaign(plan: NmcCampaignPlan, context: RunContext) -> NmcCampaignValidation:
    """Validate all declared stage outputs in deterministic graph order.

    This function never submits a model or scheduler job. It is intended for
    final evidence collection after a local, simpleWorkflow, ecFlow, or Cylc
    campaign has already produced its artifacts.
    """
    reports = {
        name: plan.stages[name].validate_outputs(context)
        for name in plan.specification.topological_order()
    }
    return NmcCampaignValidation(reports)


def write_nmc_campaign_validation(path: Path, validation: NmcCampaignValidation) -> Path:
    """Write the campaign audit as a timestamped JSON validation record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "workflow": "bmatrix.nmc_campaign",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        **validation.to_dict(),
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
