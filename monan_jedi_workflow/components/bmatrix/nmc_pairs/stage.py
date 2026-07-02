"""Workflow stage that validates NMC pairs and publishes a BFLOW manifest."""

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
    """Validate forecast pairs and publish the BFLOW hand-off manifest.

    Parameters
    ----------
    settings : NmcPairsSettings
        User-facing NMC campaign settings.
    layout : MpasForecastProductLayout
        Explicit MPAS product-layout contract used to locate restart and state
        files for every requested initialization and lead time.

    Notes
    -----
    This stage intentionally does not run MPAS. Model initialization and forecast
    execution belong to the MPAS component and are upstream dependencies. The
    NMC stage accepts already produced MPAS products, validates their scientific
    pair geometry, and publishes an implementation-independent hand-off artifact.
    """

    _SPEC = StageSpec(
        name="nmc_pairs",
        command="bmatrix.nmc_pairs",
        description="Validate MPAS NMC forecast pairs and publish the BFLOW manifest.",
    )

    def __init__(self, settings: NmcPairsSettings, layout: MpasForecastProductLayout) -> None:
        self.settings = settings
        self.layout = layout

    @classmethod
    def from_context(cls, context: RunContext) -> "NmcPairsStage":
        """Create the stage from the fully resolved workflow configuration.

        Parameters
        ----------
        context : RunContext
            Runtime context carrying the resolved configuration.

        Returns
        -------
        NmcPairsStage
            Configured stage instance.
        """
        config: Mapping[str, object] = context.config
        return cls(
            NmcPairsSettings.from_config(config),
            MpasForecastProductLayout.from_mapping(mpas_product_settings(config)),
        )

    @property
    def spec(self) -> StageSpec:
        """Return the scheduler-neutral declaration for this stage."""
        return self._SPEC

    @property
    def manifest_path(self) -> Path:
        """Return the workspace-relative BFLOW manifest path after preparation."""
        return self._workspace / self.settings.manifest_relative_path

    @property
    def report_path(self) -> Path:
        """Return the workspace-relative validation report path after preparation."""
        return self._workspace / self.settings.report_relative_path

    def _set_workspace(self, context: RunContext) -> None:
        """Bind one call lifecycle to its explicit workspace.

        The stage does not derive output locations from the process directory;
        the `RunContext` is the only source of output placement.
        """
        self._workspace = context.workspace

    def pairs(self) -> tuple[NmcPair, ...]:
        """Resolve the complete planned NMC pair set.

        Returns
        -------
        tuple[NmcPair, ...]
            Forecast pairs ordered by common valid time.
        """
        return plan_pairs(
            self.settings.valid_times(),
            older_lead_hours=self.settings.older_lead_hours,
            newer_lead_hours=self.settings.newer_lead_hours,
            resolve_forecast=self.layout.forecast,
        )

    def _manifest(self, pairs: tuple[NmcPair, ...]) -> BflowManifest:
        """Convert validated pair products to the stable BFLOW hand-off format."""
        return BflowManifest(
            tuple(
                BflowManifestEntry(pair.valid_time, pair.older.state, pair.newer.state)
                for pair in pairs
            )
        )

    def plan(self, context: RunContext) -> StageResult:
        """Describe expected pair count and hand-off artifact paths.

        Parameters
        ----------
        context : RunContext
            Resolved workflow run context.

        Returns
        -------
        StageResult
            Plan summary containing the intended manifest and report paths.
        """
        self._set_workspace(context)
        pairs = self.pairs()
        return StageResult(
            message=(
                f"Plan {len(pairs)} NMC pair(s) from {self.settings.start_valid_time} "
                f"to {self.settings.end_valid_time}."
            ),
            artifacts=(self.manifest_path, self.report_path),
        )

    def validate_inputs(self, context: RunContext) -> ValidationReport:
        """Validate required restart and MPAS state products before publication.

        Parameters
        ----------
        context : RunContext
            Resolved workflow run context.

        Returns
        -------
        ValidationReport
            Pair count, ordering, and product-availability findings.
        """
        self._set_workspace(context)
        return validate_pairs(self.pairs(), minimum_pairs=self.settings.minimum_pairs, require_products=True)

    def prepare(self, context: RunContext) -> StageResult:
        """Create deterministic parent directories for hand-off artifacts.

        Parameters
        ----------
        context : RunContext
            Resolved workflow run context.

        Returns
        -------
        StageResult
            Preparation summary.
        """
        self._set_workspace(context)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        return StageResult(message=f"Prepared NMC pair workspace: {self.manifest_path.parent}.")

    def run(self, context: RunContext) -> StageResult:
        """Write the BFLOW manifest and its successful validation report.

        Parameters
        ----------
        context : RunContext
            Resolved workflow run context.

        Returns
        -------
        StageResult
            Published manifest and report paths.
        """
        self._set_workspace(context)
        pairs = self.pairs()
        report = validate_pairs(pairs, minimum_pairs=self.settings.minimum_pairs, require_products=True)
        report.require_valid()
        manifest = write_bflow_manifest(self.manifest_path, self._manifest(pairs))
        self.report_path.write_text(
            json.dumps(
                {
                    "stage": self.spec.name,
                    "minimum_pairs": self.settings.minimum_pairs,
                    "pair_count": len(pairs),
                    "manifest": str(manifest),
                    "validation": report.to_dict(),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return StageResult(
            message=f"Published BFLOW manifest with {len(pairs)} NMC pair(s).",
            artifacts=(manifest, self.report_path),
        )

    def validate_outputs(self, context: RunContext) -> ValidationReport:
        """Validate the published manifest and the files it references.

        Parameters
        ----------
        context : RunContext
            Resolved workflow run context.

        Returns
        -------
        ValidationReport
            Manifest and state-file validation report.
        """
        self._set_workspace(context)
        if not self.manifest_path.is_file():
            report = ValidationReport(subject="nmc_pairs:outputs")
            report.add("nmc.manifest_missing", f"BFLOW manifest is missing: {self.manifest_path}")
            return report
        try:
            manifest = read_bflow_manifest(self.manifest_path)
        except Exception as exc:
            report = ValidationReport(subject="nmc_pairs:outputs")
            report.add("nmc.manifest_invalid", str(exc), path=str(self.manifest_path))
            return report
        return validate_bflow_manifest(manifest, minimum_pairs=self.settings.minimum_pairs, require_files=True)

    def finalize(self, context: RunContext) -> StageResult:
        """Record stage completion after output validation.

        Parameters
        ----------
        context : RunContext
            Resolved workflow run context.

        Returns
        -------
        StageResult
            Completion summary with published artifacts.
        """
        self._set_workspace(context)
        return StageResult(
            message=f"Finalized NMC pairs: {self.manifest_path}.",
            artifacts=(self.manifest_path, self.report_path),
        )
