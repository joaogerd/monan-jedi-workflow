"""NMC pair validation and BFLOW manifest publication stage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from ....core.stage import RunContext, Stage, StageResult
from ....core.validation import ValidationReport
from ....core.workflow_spec import StageSpec
from ...model.mpas.products import MpasForecastProductLayout
from .config import NmcPairsSettings, mpas_product_settings
from .manifest import BflowManifest, BflowManifestEntry, read_bflow_manifest, write_bflow_manifest
from .model import NmcPair, plan_pairs
from .validation import validate_bflow_manifest, validate_pairs


class NmcPairsStage(Stage):
    """Validate existing MPAS NMC pairs and publish a BFLOW manifest."""

    _SPEC = StageSpec("nmc_pairs", "bmatrix.nmc_pairs", description="Validate MPAS NMC pairs and publish the BFLOW manifest.")

    def __init__(self, settings: NmcPairsSettings, layout: MpasForecastProductLayout) -> None:
        self.settings = settings
        self.layout = layout
        self.workspace: Path | None = None

    @classmethod
    def from_context(cls, context: RunContext) -> "NmcPairsStage":
        """Create the stage from resolved configuration.

        Parameters
        ----------
        context : RunContext
            Resolved run context.
        """
        config: Mapping[str, object] = context.config
        return cls(NmcPairsSettings.from_config(config), MpasForecastProductLayout.from_mapping(mpas_product_settings(config)))

    @property
    def spec(self) -> StageSpec:
        """Return the scheduler-neutral declaration."""
        return self._SPEC

    def _bind(self, context: RunContext) -> None:
        """Bind the explicit workspace from `context`."""
        self.workspace = context.workspace

    def _output(self, relative: Path) -> Path:
        """Resolve a configured relative output path.

        Raises
        ------
        RuntimeError
            Raised before a workspace has been bound.
        """
        if self.workspace is None:
            raise RuntimeError("NMC pairs stage has no bound workspace.")
        return self.workspace / relative

    def pairs(self) -> tuple[NmcPair, ...]:
        """Resolve all configured pair identities."""
        return plan_pairs(self.settings.valid_times(), older_lead_hours=self.settings.older_lead_hours, newer_lead_hours=self.settings.newer_lead_hours, resolve_forecast=self.layout.forecast)

    def _manifest(self, pairs: tuple[NmcPair, ...]) -> BflowManifest:
        """Translate pair state files into the stable hand-off manifest."""
        return BflowManifest(tuple(BflowManifestEntry(pair.valid_time, pair.older.state, pair.newer.state) for pair in pairs))

    def plan(self, context: RunContext) -> StageResult:
        """Plan outputs without touching forecast products."""
        self._bind(context)
        return StageResult("Plan NMC pairs.", (self._output(self.settings.manifest_relative_path), self._output(self.settings.report_relative_path)))

    def validate_inputs(self, context: RunContext) -> ValidationReport:
        """Validate all restart and MPAS state products."""
        self._bind(context)
        return validate_pairs(self.pairs(), minimum_pairs=self.settings.minimum_pairs, require_products=True)

    def prepare(self, context: RunContext) -> StageResult:
        """Create output directories."""
        self._bind(context)
        self._output(self.settings.manifest_relative_path).parent.mkdir(parents=True, exist_ok=True)
        self._output(self.settings.report_relative_path).parent.mkdir(parents=True, exist_ok=True)
        return StageResult("Prepared NMC pair workspace.")

    def run(self, context: RunContext) -> StageResult:
        """Publish a manifest after complete input validation."""
        self._bind(context)
        pairs = self.pairs()
        report = validate_pairs(pairs, minimum_pairs=self.settings.minimum_pairs, require_products=True)
        report.require_valid()
        manifest = write_bflow_manifest(self._output(self.settings.manifest_relative_path), self._manifest(pairs))
        report_path = self._output(self.settings.report_relative_path)
        report_path.write_text(json.dumps({"stage": self.spec.name, "manifest": str(manifest), "validation": report.to_dict()}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return StageResult(f"Published BFLOW manifest with {len(pairs)} NMC pair(s).", (manifest, report_path))

    def validate_outputs(self, context: RunContext) -> ValidationReport:
        """Validate the full reusable NMC hand-off contract."""
        self._bind(context)
        pairs = self.pairs()
        report = validate_pairs(pairs, minimum_pairs=self.settings.minimum_pairs, require_products=True)
        manifest_path = self._output(self.settings.manifest_relative_path)
        report_path = self._output(self.settings.report_relative_path)
        if not manifest_path.is_file():
            report.add("nmc.manifest_missing", f"BFLOW manifest is missing: {manifest_path}")
        else:
            try:
                manifest = read_bflow_manifest(manifest_path)
            except Exception as exc:
                report.add("nmc.manifest_invalid", str(exc), path=str(manifest_path))
            else:
                if manifest != self._manifest(pairs):
                    report.add("nmc.manifest_contract", "Published BFLOW manifest does not match the current NMC pair plan.", path=str(manifest_path))
                report.issues.extend(validate_bflow_manifest(manifest, minimum_pairs=self.settings.minimum_pairs, require_files=True).issues)
        if not report_path.is_file():
            report.add("nmc.report_missing", f"Validation report is missing: {report_path}")
        return report

    def finalize(self, context: RunContext) -> StageResult:
        """Return published artifact paths after validation."""
        self._bind(context)
        return StageResult("Finalized NMC pairs.", (self._output(self.settings.manifest_relative_path), self._output(self.settings.report_relative_path)))
