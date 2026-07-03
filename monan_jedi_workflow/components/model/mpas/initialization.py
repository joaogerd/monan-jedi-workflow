"""MPAS initialization products and executable stage."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from string import Formatter
from typing import Mapping
from xml.etree import ElementTree

from ....core.stage import RunContext, StageResult
from ....core.workflow_spec import StageSpec
from ....platforms.base import ExecutionBackend, ExecutionRequest
from .execution_stage import MpasExecutionStage
from .output_validation import MpasOutputContract
from .products import MPAS_TIME_FORMAT, MpasProductLayoutError, normalize_mpas_time
from .staging import LinkSpec, TemplateSpec


_MESH_OUTPUT_PREFIX = re.compile(r"^x\d+\.\d+(?=\.)")


def mpas_initialization_context(cycle_time: str) -> dict[str, str | int]:
    """Build canonical template values for one MPAS initialization."""
    normalized = normalize_mpas_time(cycle_time)
    cycle = datetime.strptime(normalized, MPAS_TIME_FORMAT)
    return {
        "cycle_time": normalized,
        "init_time": normalized,
        "valid_time": normalized,
        "init_yyyymmddhh": cycle.strftime("%Y%m%d%H"),
        "valid_yyyymmddhh": cycle.strftime("%Y%m%d%H"),
        "mpas_valid_file_time": cycle.strftime("%Y-%m-%d_%H.%M.%S"),
        "wps_time": cycle.strftime("%Y-%m-%d_%H"),
        "lead_hours": 0,
        "lead_hours_03d": "000",
    }


@dataclass(frozen=True)
class MpasInitializationProduct:
    """Describe the state created for one MPAS initialization time."""

    cycle_time: str
    state: Path

    def __post_init__(self) -> None:
        """Normalize the cycle time through the shared MPAS time contract."""
        try:
            object.__setattr__(self, "cycle_time", normalize_mpas_time(self.cycle_time))
        except MpasProductLayoutError as exc:
            raise ValueError(str(exc)) from exc


@dataclass(frozen=True)
class MpasInitializationProductLayout:
    """Resolve initial MPAS state files from an explicit path template."""

    root: Path
    state_template: str

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "MpasInitializationProductLayout":
        """Build a layout from `model.mpas.initialization_products` settings."""
        try:
            root = values["root"]
            state = values["state_template"]
        except KeyError as exc:
            raise MpasProductLayoutError(f"model.mpas.initialization_products missing {exc.args[0]}.") from exc
        if not isinstance(root, str) or not root or not isinstance(state, str) or not state:
            raise MpasProductLayoutError("MPAS initialization product settings must be non-empty strings.")
        return cls(Path(root), state)

    def __post_init__(self) -> None:
        """Reject implicit roots and undocumented state-template placeholders."""
        if not self.root.is_absolute():
            raise MpasProductLayoutError("MPAS initialization_products.root must be an absolute path.")
        allowed = set(mpas_initialization_context("2000-01-01_00:00:00"))
        names = {name for _, name, _, _ in Formatter().parse(self.state_template) if name}
        unknown = names.difference(allowed)
        if unknown:
            raise MpasProductLayoutError(
                f"unsupported field(s) in MPAS initialization path template: {', '.join(sorted(unknown))}."
            )

    def initialize(self, cycle_time: str) -> MpasInitializationProduct:
        """Resolve the initial MPAS state artifact for one cycle time."""
        values = mpas_initialization_context(cycle_time)
        path = Path(self.state_template.format_map(values))
        return MpasInitializationProduct(str(values["cycle_time"]), path if path.is_absolute() else self.root / path)


def _replace_namelist_assignment(text: str, name: str, value: str) -> str:
    """Replace one required Fortran namelist assignment without reformatting it."""
    pattern = re.compile(rf"^(?P<prefix>\s*{re.escape(name)}\s*=\s*)(?P<old>[^!\n]*?)(?P<suffix>\s*(?:!.*)?$)", re.MULTILINE)
    updated, count = pattern.subn(lambda match: f"{match.group('prefix')}{value}{match.group('suffix')}", text, count=1)
    if count != 1:
        raise RuntimeError(f"MPAS initialization namelist is missing required assignment: {name}")
    return updated


class MpasInitializationStage(MpasExecutionStage):
    """Execute MPAS initialization and publish one initial state artifact."""

    def __init__(self, product: MpasInitializationProduct, run_dir: Path, contract: MpasOutputContract, *, request: ExecutionRequest | None = None, backend: ExecutionBackend | None = None, links: tuple[LinkSpec, ...] = (), templates: tuple[TemplateSpec, ...] = ()) -> None:
        self.product = product
        token = mpas_initialization_context(product.cycle_time)["init_yyyymmddhh"]
        spec = StageSpec(f"mpas_init_{token}", "model.mpas.initialize", description="Execute MPAS initialization and validate the initial state.")
        files = (product.state, *contract.required_files)
        values = {**mpas_initialization_context(product.cycle_time), "state": str(product.state)}
        super().__init__(
            spec,
            run_dir,
            MpasOutputContract(files, contract.log_path, contract.required_log_markers, contract.netcdf_checks),
            request=request,
            backend=backend,
            links=links,
            templates=templates,
            values=values,
            artifacts=(product.state,),
        )

    def _mesh_filename(self) -> str:
        """Return the declared MPAS bootstrap filename exposed by staging."""
        for link in self.links:
            if link.target.name.endswith(".grid.nc"):
                return link.target.name
        raise RuntimeError("MPAS initialization with WPS forcing requires an explicit *.grid.nc bootstrap link.")

    @staticmethod
    def _stream(root: ElementTree.Element, name: str) -> ElementTree.Element:
        """Return one required immutable stream by logical name."""
        stream = next((item for item in root.iter("immutable_stream") if item.get("name") == name), None)
        if stream is None:
            raise RuntimeError(f"MPAS initialization stream template lacks required {name!r} immutable stream.")
        return stream

    @staticmethod
    def _mesh_identifier(mesh_filename: str) -> str:
        """Return the mesh stem used by MPAS output filenames."""
        suffix = ".grid.nc"
        if not mesh_filename.endswith(suffix):
            raise RuntimeError(f"MPAS initialization mesh filename must end with {suffix}: {mesh_filename}")
        return mesh_filename[: -len(suffix)]

    @staticmethod
    def _patch_auxiliary_output_mesh_names(root: ElementTree.Element, mesh_identifier: str) -> None:
        """Replace legacy mesh prefixes in auxiliary init output stream names only."""
        for stream in root.iter("immutable_stream"):
            if stream.get("type") != "output":
                continue
            template = stream.get("filename_template")
            if template is None:
                continue
            stream.set("filename_template", _MESH_OUTPUT_PREFIX.sub(mesh_identifier, template, count=1))

    def _static_fields_mode(self) -> str:
        """Return the explicit static-fields strategy required for WPS-backed init."""
        mode = self.values.get("static_fields_mode")
        if mode not in {"invariant", "interpolate_geography"}:
            raise RuntimeError(
                "MPAS initialization with WPS forcing requires static_fields.mode to be 'invariant' or 'interpolate_geography'."
            )
        return str(mode)

    def _require_invariant_bootstrap_link(self, mesh_filename: str) -> None:
        """Require that the rendered bootstrap name resolves to declared invariant data."""
        source = self.values.get("static_fields_source")
        target = self.values.get("static_fields_target")
        if not isinstance(source, str) or not isinstance(target, str):
            raise RuntimeError("MPAS invariant static-fields mode requires declared source and target.")
        if target != mesh_filename:
            raise RuntimeError(
                f"MPAS invariant static-fields target must match bootstrap stream {mesh_filename!r}, got {target!r}."
            )
        expected_source = Path(source)
        if not expected_source.name.endswith(".invariant.nc"):
            raise RuntimeError(f"MPAS invariant static-fields source must end with '.invariant.nc': {expected_source}")
        if not any(link.source == expected_source and link.target.name == target for link in self.links):
            raise RuntimeError(
                f"MPAS invariant static-fields link is missing: {expected_source} -> {self.run_dir / target}"
            )

    def _geog_data_path(self) -> Path:
        """Return one declared local geographical-data root for interpolation mode."""
        configured = self.values.get("geog_data_path")
        if not isinstance(configured, str) or not configured:
            raise RuntimeError("MPAS geographical interpolation requires declared geog_data_path.")
        path = Path(configured)
        if not path.is_absolute():
            raise RuntimeError("MPAS initialization geog_data_path must be absolute.")
        if not path.is_dir():
            raise RuntimeError(f"MPAS initialization geog_data_path does not exist: {path}")
        return path

    def _require_geog_datasets(self, root: Path) -> None:
        """Require declared geodata directories to expose WPS `index` files."""
        datasets = self.values.get("geog_required_datasets", ())
        if not isinstance(datasets, tuple) or not datasets or not all(isinstance(item, str) and item for item in datasets):
            raise RuntimeError("MPAS interpolation mode requires geog_required_datasets as non-empty dataset names.")
        for dataset in datasets:
            index = root / dataset / "index"
            if not index.is_file():
                raise RuntimeError(f"MPAS initialization geographical dataset is missing index: {index}")

    def _patch_streams(self, mesh_filename: str) -> None:
        """Render mesh bootstrap and mesh-specific initialization output filenames."""
        streams = self.run_dir / "streams.init_atmosphere"
        if not streams.is_file():
            raise RuntimeError(f"MPAS initialization stream patch requires: {streams}")
        tree = ElementTree.parse(streams)
        root = tree.getroot()
        input_stream = self._stream(root, "input")
        output_stream = self._stream(root, "output")
        self._patch_auxiliary_output_mesh_names(root, self._mesh_identifier(mesh_filename))
        input_stream.set("filename_template", mesh_filename)
        input_stream.set("input_interval", "initial_only")
        output_stream.set("filename_template", self.product.state.name)
        output_stream.set("output_interval", "initial_only")
        if input_stream.get("filename_template") != mesh_filename:
            raise RuntimeError("MPAS initialization stream renderer failed to bind the declared mesh filename.")
        if output_stream.get("filename_template") != self.product.state.name:
            raise RuntimeError("MPAS initialization stream renderer failed to bind the declared state filename.")
        tree.write(streams, encoding="unicode")

    def _patch_namelist(self, values: Mapping[str, str]) -> None:
        """Render mandatory initialization settings into the installed namelist."""
        namelist = self.run_dir / "namelist.init_atmosphere"
        if not namelist.is_file():
            raise RuntimeError(f"MPAS initialization namelist patch requires: {namelist}")
        rendered = namelist.read_text(encoding="utf-8")
        for name, value in values.items():
            rendered = _replace_namelist_assignment(rendered, name, value)
        namelist.write_text(rendered, encoding="utf-8")

    def _base_wps_namelist_values(self) -> dict[str, str]:
        """Return namelist settings shared by every WPS-backed initialization."""
        prefix = self.values.get("decomposition_prefix")
        if not isinstance(prefix, str) or not prefix.endswith(".graph.info.part."):
            raise RuntimeError("MPAS initialization requires a declared graph decomposition prefix for WPS forcing.")
        return {
            "config_init_case": "7",
            "config_start_time": f"'{self.product.cycle_time}'",
            "config_stop_time": f"'{self.product.cycle_time}'",
            "config_met_prefix": "'FILE'",
            "config_fg_interval": "86400",
            "config_block_decomp_file_prefix": f"'{prefix}'",
        }

    def _patch_invariant_namelist(self) -> None:
        """Render the validated invariant-static baseline used by MPAS forecasts."""
        values = {
            **self._base_wps_namelist_values(),
            "config_sfc_prefix": "'FILE'",
            "config_static_interp": ".false.",
            "config_native_gwd_static": ".false.",
            "config_native_gwd_gsl_static": ".false.",
            "config_vertical_grid": ".true.",
            "config_met_interp": ".true.",
        }
        self._patch_namelist(values)

    def _patch_geography_namelist(self, geog_data_path: Path) -> None:
        """Render the explicit geographical-interpolation strategy."""
        values = {
            **self._base_wps_namelist_values(),
            "config_geog_data_path": f"'{geog_data_path}/'",
        }
        self._patch_namelist(values)

    def _require_wps_forcing_link(self, forcing: str) -> None:
        """Require the declared WPS intermediate link without treating it as mesh."""
        if not any(link.target.name == forcing and link.upstream_artifact for link in self.links):
            raise RuntimeError(f"MPAS initialization is missing declared upstream WPS forcing link: {forcing}")

    def prepare(self, context: RunContext) -> StageResult:
        """Stage WPS forcing, static fields, and cycle-specific initialization settings."""
        result = super().prepare(context)
        forcing = self.values.get("met_input_filename")
        if forcing is None:
            return result
        if not isinstance(forcing, str) or not forcing.startswith("FILE:"):
            raise RuntimeError("MPAS initialization met_input_filename must use the WPS FILE: prefix.")
        self._require_wps_forcing_link(forcing)
        mesh_filename = self._mesh_filename()
        mode = self._static_fields_mode()
        self._patch_streams(mesh_filename)
        if mode == "invariant":
            self._require_invariant_bootstrap_link(mesh_filename)
            self._patch_invariant_namelist()
        else:
            geog_data_path = self._geog_data_path()
            self._require_geog_datasets(geog_data_path)
            self._patch_geography_namelist(geog_data_path)
        return result
