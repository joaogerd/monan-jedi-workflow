"""NMC pair validation and BFLOW manifest publication stage."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from ....core.netcdf_validation import validate_netcdf_structure
from ....core.stage import RunContext, Stage, StageResult
from ....core.validation import ValidationReport
from ....core.workflow_spec import StageSpec
from ...model.mpas.netcdf_contracts import mpas_artifact_check
from ...model.mpas.products import MpasForecastProductLayout
from .config import NmcPairsSettings, mpas_product_settings
from .manifest import BflowManifest, BflowManifestEntry, read_bflow_manifest, write_bflow_manifest
from .model import NmcPair, plan_pairs
from .validation import validate_bflow_manifest, validate_pairs


class NmcPairsStage(Stage):
    """Validate existing MPAS NMC pairs and publish a BFLOW manifest."""

    _SPEC = StageSpec("nmc_pairs", "bmatrix.nmc_pairs", description="Validate MPAS NMC pairs and publish the BFLOW manifest.")

    def __init__(
        self,
        settings: NmcPairsSettings,
        layout: MpasForecastProductLayout,
        config: Mapping[str, object],
    ) -> None:
        self.settings = settings
        self.layout = layout
        self.config = config
        self.workspace: Path | None = None

    @classmethod
    def from_context(cls, context: RunContext) -> "NmcPairsStage":
        """Create the stage from resolved configuration."""
        config: Mapping[str, object] = context.config
        return cls(
            NmcPairsSettings.from_config(config),
            MpasForecastProductLayout.from_mapping(mpas_product_settings(config)),
            config,
        )

    @property
    def spec(self) -> StageSpec:
        """Return the scheduler-neutral declaration."""
        return self._SPEC

    def _bind(self, context: RunContext) -> None:
        """Bind the explicit workspace from `context`."""
        self.workspace = context.workspace

    def _output(self, relative: Path) -> Path:
        """Resolve a configured relative output path."""
        if self.workspace is None:
            raise RuntimeError("NMC pairs stage has no bound workspace.")
        return self.workspace / relative

    def pairs(self) -> tuple[NmcPair, ...]:
        """Resolve all configured pair identities."""
        return plan_pairs(
            self.settings.valid_times(),
            older_lead_hours=self.settings.older_lead_hours,
            newer_lead_hours=self.settings.newer_lead_hours,
            resolve_forecast=self.layout.forecast,
        )

    def _validate_netcdf(self, pairs: tuple[NmcPair, ...]) -> ValidationReport:
        """Validate optional restart/state structural contracts for every pair."""
        report = ValidationReport(subject="nmc_pairs:netcdf")
        for pair in pairs:
            for member in (pair.older, pair.newer):
                for name, path in (("forecast_restart", member.restart), ("forecast_state", member.state)):
                    check = mpas_artifact_check(
                        self.config,
                        name=name,
                        path=path,
                        default_consumer="bmatrix.bflow",
                        expected_time=pair.valid_time,
                    )
                    if check is not None:
                        report.issues.extend(validate_netcdf_structure(path, check.contract).issues)
        return report

    def _validate_inputs(self, pairs: tuple[NmcPair, ...]) -> ValidationReport:
        """Validate pair geometry, required products, and optional NetCDF contracts."""
        report = validate_pairs(pairs, minimum_pairs=self.settings.minimum_pairs, require_products=True)
        report.issues.extend(self._validate_netcdf(pairs).issues)
        return report

    def _manifest(self, pairs: tuple[NmcPair, ...]) -> BflowManifest:
        """Translate pair state files into the stable hand-off manifest."""
        return BflowManifest(tuple(BflowManifestEntry(pair.valid_time, pair.older.state, pair.newer.state) for pair in pairs))

    def plan(self, context: RunContext) -> StageResult:
        """Plan outputs without touching forecast products."""
        self._bind(context)
        return StageResult("Plan NMC pairs.", (self._output(self.settings.manifest_relative_path), self._output(self.settings.report_relative_path)))

    def validate_inputs(self, context: RunContext) -> ValidationReport:
        """Validate all restart and MPAS state products before publication."""
        self._bind(context)
        return self._validate_inputs(self.pairs())

    def validate_preparation_inputs(self, context: RunContext) -> ValidationReport:
        """Validate only NMC pair geometry before forecast products are produced."""
        self._bind(context)
        return validate_pairs(self.pairs(), minimum_pairs=self.settings.minimum_pairs, require_products=False)

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
        report = self._validate_inputs(pairs)
        report.require_valid()
        manifest = write_bflow_manifest(self._output(self.settings.manifest_relative_path), self._manifest(pairs))
        report_path = self._output(self.settings.report_relative_path)
        report_path.write_text(
            json.dumps({"stage": self.spec.name, "manifest": str(manifest), "validation": report.to_dict()}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return StageResult(f"Published BFLOW manifest with {len(pairs)} NMC pair(s).", (manifest, report_path))

    def validate_outputs(self, context: RunContext) -> ValidationReport:
        """Validate the full reusable NMC hand-off contract."""
        self._bind(context)
        pairs = self.pairs()
        report = self._validate_inputs(pairs)
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
