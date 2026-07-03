"""MPAS forecast specialization of the reusable execution stage."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from xml.etree import ElementTree

from ....core.stage import RunContext, StageResult
from ....core.workflow_spec import StageSpec
from ....platforms.base import ExecutionBackend, ExecutionRequest
from .execution_stage import MpasExecutionStage
from .output_validation import MpasOutputContract
from .products import MpasForecastProduct, mpas_time_context
from .staging import LinkSpec, TemplateSpec


def _assignment_pattern(name: str) -> re.Pattern[str]:
    """Return one anchored Fortran-namelist assignment pattern."""
    return re.compile(
        rf"^(?P<prefix>\s*{re.escape(name)}\s*=\s*)(?P<old>[^!\n]*?)(?P<suffix>\s*(?:!.*)?$)",
        re.MULTILINE,
    )


def _replace_namelist_assignment(text: str, name: str, value: str) -> str:
    """Replace a required Fortran namelist assignment without reformatting it."""
    updated, count = _assignment_pattern(name).subn(
        lambda match: f"{match.group('prefix')}{value}{match.group('suffix')}",
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError(f"MPAS forecast namelist is missing required assignment: {name}")
    return updated


def _has_assignment(text: str, name: str) -> bool:
    """Return whether a namelist template defines a named assignment."""
    return _assignment_pattern(name).search(text) is not None


class MpasForecastStage(MpasExecutionStage):
    """Execute one MPAS forecast and publish restart and state products."""

    def __init__(
        self,
        product: MpasForecastProduct,
        run_dir: Path,
        contract: MpasOutputContract,
        *,
        request: ExecutionRequest | None = None,
        backend: ExecutionBackend | None = None,
        links: tuple[LinkSpec, ...] = (),
        templates: tuple[TemplateSpec, ...] = (),
        extra_values: Mapping[str, object] | None = None,
    ) -> None:
        self.product = product
        token = mpas_time_context(product.init_time, product.lead_hours)["init_yyyymmddhh"]
        spec = StageSpec(
            name=f"mpas_forecast_{token}_f{product.lead_hours:03d}",
            command="model.mpas.forecast",
            description="Execute one MPAS forecast and validate restart/state products.",
        )
        files = (product.restart, product.state, *contract.required_files)
        values: dict[str, object] = {
            "init_time": product.init_time,
            "valid_time": product.valid_time,
            "init_yyyymmddhh": product.init_time.replace("-", "").replace("_", "")[:10],
            "valid_yyyymmddhh": product.valid_time.replace("-", "").replace("_", "")[:10],
            "mpas_valid_file_time": product.valid_time.replace(":", "."),
            "lead_hours": product.lead_hours,
            "lead_hours_03d": f"{product.lead_hours:03d}",
            "restart": str(product.restart),
            "state": str(product.state),
        }
        upstream = dict(extra_values or {})
        collision = set(values).intersection(upstream)
        if collision:
            raise ValueError(f"MPAS forecast extra values cannot override product tokens: {', '.join(sorted(collision))}.")
        values.update(upstream)
        super().__init__(
            spec,
            run_dir,
            MpasOutputContract(
                required_files=files,
                log_path=contract.log_path,
                required_log_markers=contract.required_log_markers,
                netcdf_checks=contract.netcdf_checks,
            ),
            request=request,
            backend=backend,
            links=links,
            templates=templates,
            values=values,
            artifacts=(product.restart, product.state),
        )

    def _initial_state_link(self) -> LinkSpec | None:
        """Return the explicit initialization-state link, when present."""
        return next((link for link in self.links if link.upstream_artifact), None)

    def _decomposition_prefix(self) -> str | None:
        """Derive the partition prefix from a declared graph-partition link."""
        for link in self.links:
            name = link.target.name
            if ".graph.info.part." not in name:
                continue
            stem, separator, ranks = name.rpartition(".")
            if separator and ranks.isdigit():
                return f"{stem}."
        return None

    @staticmethod
    def _stream(root: ElementTree.Element, name: str, tag: str = "immutable_stream") -> ElementTree.Element:
        """Return or create one named stream element with the requested tag."""
        stream = next((item for item in root.iter() if item.get("name") == name), None)
        if stream is not None:
            return stream
        return ElementTree.SubElement(root, tag, {"name": name})

    def _invariant_filename(self) -> str | None:
        """Return the run-local invariant filename when explicitly staged."""
        for link in self.links:
            if link.target.name.endswith(".invariant.nc"):
                return link.target.name
        return None

    def _patch_streams(self, initial_state: LinkSpec) -> None:
        """Bind validated producer-baseline streams to explicit V2 artifacts."""
        streams = self.run_dir / "streams.atmosphere"
        if not streams.is_file():
            return
        tree = ElementTree.parse(streams)
        root = tree.getroot()

        input_stream = self._stream(root, "input")
        input_stream.set("type", "input")
        input_stream.set("filename_template", initial_state.target.name)
        input_stream.set("input_interval", "initial_only")

        interval = self.values.get("forecast_output_interval")
        if interval is not None:
            if not isinstance(interval, str) or not interval:
                raise RuntimeError("MPAS forecast_output_interval must be a non-empty string when declared.")
            invariant = self._invariant_filename()
            if invariant is None:
                raise RuntimeError("MPAS forecast producer baseline requires a declared *.invariant.nc link.")
            invariant_stream = self._stream(root, "invariant")
            invariant_stream.set("type", "input")
            invariant_stream.set("filename_template", invariant)
            invariant_stream.set("input_interval", "initial_only")

            da_state = self._stream(root, "da_state")
            da_state.set("type", "output")
            da_state.set("precision", da_state.get("precision", "single"))
            da_state.set("io_type", da_state.get("io_type", "pnetcdf,cdf5"))
            da_state.set("filename_template", "mpasout.$Y-$M-$D_$h.$m.$s.nc")
            da_state.set("packages", "jedi_da")
            da_state.set("output_interval", interval)
            da_state.set("filename_interval", "output_interval")
            da_state.set("clobber_mode", "overwrite")

            restart = self._stream(root, "restart", tag="stream")
            restart.set("type", "output")
            restart.set("filename_template", "restart.$Y-$M-$D_$h.$m.$s.nc")
            restart.set("filename_interval", "output_interval")
            restart.set("output_interval", interval)
            restart.set("clobber_mode", "overwrite")

            for name in ("output", "diagnostics"):
                stream = next((item for item in root.iter() if item.get("name") == name), None)
                if stream is not None:
                    stream.set("type", "none")
                    stream.set("output_interval", "none")

        tree.write(streams, encoding="unicode")

    def _duration(self) -> str:
        """Render the MPAS `D_HH:MM:SS` duration for this forecast lead."""
        days, hours = divmod(self.product.lead_hours, 24)
        return f"'{days}_{hours:02d}:00:00'"

    def _patch_namelist(self, decomposition_prefix: str | None) -> None:
        """Render cycle, duration, decomposition, and declared baseline values."""
        namelist = self.run_dir / "namelist.atmosphere"
        if not namelist.is_file():
            return
        if decomposition_prefix is None:
            raise RuntimeError("MPAS forecast namelist rendering requires a declared graph partition link.")
        rendered = namelist.read_text(encoding="utf-8")
        replacements: dict[str, str] = {
            "config_start_time": f"'{self.product.init_time}'",
            "config_block_decomp_file_prefix": f"'{decomposition_prefix}'",
            "config_do_restart": ".false.",
        }
        overrides = self.values.get("forecast_namelist_overrides", {})
        if not isinstance(overrides, Mapping) or not all(isinstance(name, str) and isinstance(value, str) for name, value in overrides.items()):
            raise RuntimeError("MPAS forecast_namelist_overrides must be a string mapping.")
        protected = set(replacements)
        collision = protected.intersection(overrides)
        if collision:
            raise RuntimeError(
                "MPAS forecast_namelist_overrides cannot replace generated values: " + ", ".join(sorted(collision))
            )
        replacements.update(overrides)
        for name, value in replacements.items():
            rendered = _replace_namelist_assignment(rendered, name, value)
        if _has_assignment(rendered, "config_stop_time"):
            rendered = _replace_namelist_assignment(rendered, "config_stop_time", f"'{self.product.valid_time}'")
        elif _has_assignment(rendered, "config_run_duration"):
            rendered = _replace_namelist_assignment(rendered, "config_run_duration", self._duration())
        else:
            raise RuntimeError("MPAS forecast namelist must define config_stop_time or config_run_duration.")
        namelist.write_text(rendered, encoding="utf-8")

    def prepare(self, context: RunContext) -> StageResult:
        """Stage inputs and render files for the exact init-time and lead."""
        result = super().prepare(context)
        initial_state = self._initial_state_link()
        if initial_state is None:
            return result
        self._patch_streams(initial_state)
        self._patch_namelist(self._decomposition_prefix())
        return result
