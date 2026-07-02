"""V2 WPS GRIB-to-FILE producer used by MPAS initialization."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from ....core.stage import RunContext, Stage, StageResult
from ....core.validation import ValidationReport
from ....core.workflow_spec import StageSpec
from ....platforms.base import ExecutionBackend, ExecutionRequest
from ..mpas.runtime_config import MpasRuntimeConfigurationError, compile_runtime, require_mapping
from ..mpas.staging import LinkSpec, TemplateSpec, render_template, stage_link
from .products import WpsIntermediateProduct, WpsIntermediateProductLayout, WpsProductError


class WpsConfigurationError(MpasRuntimeConfigurationError):
    """Raised when the declared WPS ungrib contract is incomplete or invalid."""


@dataclass(frozen=True)
class WpsOutputContract:
    """Declare required WPS intermediate files and optional log markers."""

    required_files: tuple[Path, ...]
    log_path: Path | None = None
    required_log_markers: tuple[str, ...] = ()


def _validate_wps_outputs(run_dir: Path, contract: WpsOutputContract) -> ValidationReport:
    """Validate product presence and configured ungrib log markers."""
    report = ValidationReport(subject=f"wps_output:{run_dir}")
    for item in contract.required_files:
        path = item if item.is_absolute() else run_dir / item
        if not path.is_file() or path.stat().st_size == 0:
            report.add("wps.output_missing", f"Required WPS output is missing or empty: {path}", path=str(path))
    if contract.log_path is not None:
        path = contract.log_path if contract.log_path.is_absolute() else run_dir / contract.log_path
        if not path.is_file():
            report.add("wps.log_missing", f"Required WPS log is missing: {path}", path=str(path))
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
            for marker in contract.required_log_markers:
                if marker not in text:
                    report.add("wps.log_marker", f"WPS log marker is missing: {marker}", path=str(path))
    return report


class WpsUngribStage(Stage):
    """Run WPS `ungrib` and publish one explicit `FILE:` product."""

    def __init__(self, product: WpsIntermediateProduct, run_dir: Path, contract: WpsOutputContract, *, request: ExecutionRequest, backend: ExecutionBackend, links: tuple[LinkSpec, ...], templates: tuple[TemplateSpec, ...], values: Mapping[str, object]) -> None:
        self.product, self.run_dir, self.contract = product, run_dir, contract
        self.request, self.backend = request, backend
        self.links, self.templates, self.values = links, templates, dict(values)
        token = self.values["init_yyyymmddhh"]
        self._spec = StageSpec(f"wps_ungrib_{token}", "model.wps.ungrib", description="Transform declared GRIB inputs into one WPS FILE product.")

    @property
    def spec(self) -> StageSpec:
        """Return the scheduler-neutral ungrib declaration."""
        return self._spec

    def plan(self, context: RunContext) -> StageResult:
        """Persist a platform-resolved plan when the backend supports it."""
        resolver = getattr(self.backend, "resolve", None)
        if not callable(resolver):
            return StageResult(f"Plan {self.spec.name}.", (self.product.intermediate,))
        resolved = resolver(self.request)
        serializer = getattr(resolved, "to_dict", None)
        if not callable(serializer):
            return StageResult(f"Plan {self.spec.name}.", (self.product.intermediate,))
        record = context.workspace / ".monan-jedi-workflow" / "dry-run" / f"{self.spec.name}.json"
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(json.dumps(serializer(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        script = getattr(resolved, "script", None)
        artifacts = (self.product.intermediate, record)
        return StageResult(f"Resolved platform plan for {self.spec.name}.", (*artifacts, script) if isinstance(script, Path) else artifacts)

    def validate_inputs(self, context: RunContext) -> ValidationReport:
        """Require every declared GRIB, Vtable, and template source."""
        report = ValidationReport(subject=f"stage:{self.spec.name}:inputs")
        for item in self.links:
            if not item.source.exists():
                report.add("wps.link_source", f"WPS link source is missing: {item.source}", path=str(item.source))
        for item in self.templates:
            if not item.source.is_file():
                report.add("wps.template_source", f"WPS template is missing: {item.source}", path=str(item.source))
        return report

    def prepare(self, context: RunContext) -> StageResult:
        """Create the WPS run directory and stage declared inputs without shell scripts."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        values = {"workspace": str(context.workspace), "run_dir": str(self.run_dir), **self.values}
        for item in self.links:
            stage_link(item)
        for item in self.templates:
            render_template(item, values)
        return StageResult(f"Prepared WPS stage: {self.spec.name}.")

    def run(self, context: RunContext) -> StageResult:
        """Submit `ungrib` through the selected execution backend."""
        handle = self.backend.submit(self.request)
        self.backend.wait(handle)
        return StageResult(f"WPS ungrib completed: {handle.identifier}.")

    def validate_outputs(self, context: RunContext) -> ValidationReport:
        """Validate the published intermediate product and configured log contract."""
        return _validate_wps_outputs(self.run_dir, self.contract)

    def finalize(self, context: RunContext) -> StageResult:
        """Publish the WPS `FILE:` artifact for the matching MPAS initialization."""
        return StageResult(f"Finalized WPS stage: {self.spec.name}.", (self.product.intermediate,))


def _grib_links(section: Mapping[str, object]) -> list[dict[str, str]]:
    """Translate explicit GRIB inputs to WPS conventional `GRIBFILE.*` links."""
    raw = section.get("grib_inputs")
    if not isinstance(raw, list) or not raw:
        raise WpsConfigurationError("model.wps.ungrib.grib_inputs must be a non-empty list.")
    result: list[dict[str, str]] = []
    targets: set[str] = set()
    for index, item in enumerate(raw):
        entry = require_mapping(item, f"model.wps.ungrib.grib_inputs[{index}]")
        source, target = entry.get("source"), entry.get("target")
        if not isinstance(source, str) or not source or not isinstance(target, str) or not target.startswith("GRIBFILE."):
            raise WpsConfigurationError(f"model.wps.ungrib.grib_inputs[{index}] requires source and GRIBFILE.* target.")
        if target in targets:
            raise WpsConfigurationError(f"Duplicate WPS GRIB target: {target}.")
        targets.add(target)
        result.append({"source": source, "target": target})
    return result


def compile_wps_ungrib(config: Mapping[str, object], *, workspace: Path, init_time: str, backend: ExecutionBackend) -> WpsUngribStage:
    """Compile one explicit GRIB-to-WPS-intermediate execution stage."""
    try:
        model = require_mapping(config.get("model"), "model")
        wps = require_mapping(model.get("wps"), "model.wps")
        section = require_mapping(wps.get("ungrib"), "model.wps.ungrib")
        layout = WpsIntermediateProductLayout.from_mapping(require_mapping(wps.get("ungrib_products"), "model.wps.ungrib_products"))
        product = layout.product(init_time)
        values = {
            "workspace": str(workspace),
            "init_time": product.init_time,
            "init_yyyymmddhh": product.init_time.replace("-", "").replace("_", "")[:10],
            "wps_time": product.wps_time,
            "intermediate": str(product.intermediate),
        }
        links = section.get("links", [])
        if not isinstance(links, list):
            raise WpsConfigurationError("model.wps.ungrib.links must be a list when set.")
        augmented = dict(section)
        augmented["links"] = [*links, *_grib_links(section)]
        runtime = compile_runtime(augmented, label="model.wps.ungrib", workspace=workspace, values=values, backend=backend)
    except (MpasRuntimeConfigurationError, WpsProductError) as exc:
        raise WpsConfigurationError(str(exc)) from exc
    if product.intermediate.parent != runtime.run_dir:
        raise WpsConfigurationError("WPS intermediate product must be written directly in model.wps.ungrib.run_dir.")
    contract = WpsOutputContract((product.intermediate, *runtime.contract.required_files), runtime.contract.log_path, runtime.contract.required_log_markers)
    return WpsUngribStage(product, runtime.run_dir, contract, request=runtime.request, backend=backend, links=runtime.links, templates=runtime.templates, values=runtime.values)


__all__ = ["WpsConfigurationError", "WpsIntermediateProduct", "WpsIntermediateProductLayout", "WpsProductError", "WpsUngribStage", "compile_wps_ungrib"]
