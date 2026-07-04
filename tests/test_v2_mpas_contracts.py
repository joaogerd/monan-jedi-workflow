"""Tests for V2 MPAS contracts."""

from pathlib import Path

import pytest

from monan_jedi_workflow.components.model.mpas import (
    LinkSpec,
    MpasForecastProductLayout,
    MpasInitializationProductLayout,
    MpasOutputContract,
    MpasProductLayoutError,
    TemplateSpec,
    render_template,
    stage_link,
    validate_output_contract,
)
from monan_jedi_workflow.platforms.base import ExecutionRequest
from monan_jedi_workflow.platforms.jaci_pbs import JaciPbsResources, render_pbs


def test_mpas_product_layout_resolves_without_bmatrix_dependency(tmp_path: Path) -> None:
    """MPAS products resolve from their own component contract."""
    layout = MpasForecastProductLayout(
        tmp_path,
        "{init_yyyymmddhh}/f{lead_hours_03d}/restart.{mpas_valid_file_time}.nc",
        "{init_yyyymmddhh}/f{lead_hours_03d}/mpasout.{mpas_valid_file_time}.nc",
    )
    product = layout.forecast("2026-06-20T00:00:00Z", 48)
    assert product.valid_time == "2026-06-22_00:00:00"
    assert product.state.name == "mpasout.2026-06-22_00.00.00.nc"


def test_mpas_product_roots_must_be_absolute() -> None:
    """Product locations cannot silently depend on the current directory."""
    with pytest.raises(MpasProductLayoutError, match="absolute path"):
        MpasForecastProductLayout(Path("relative"), "restart.nc", "state.nc")
    with pytest.raises(MpasProductLayoutError, match="absolute path"):
        MpasInitializationProductLayout(Path("relative"), "init.nc")


def test_staging_and_output_contract_are_idempotent(tmp_path: Path) -> None:
    """Links, templates, and outputs use safe explicit contracts."""
    source = tmp_path / "input.nc"
    source.write_text("input", encoding="utf-8")
    target = tmp_path / "run/input.nc"
    assert stage_link(LinkSpec(source, target)) == target
    assert stage_link(LinkSpec(source, target)) == target
    template = tmp_path / "stream.in"
    template.write_text("valid={valid_time}\n", encoding="utf-8")
    rendered = tmp_path / "run/stream.in"
    render_template(TemplateSpec(template, rendered), {"valid_time": "2026-06-22_00:00:00"})
    output = tmp_path / "run/mpasout.nc"
    output.write_bytes(b"state")
    log = tmp_path / "run/stdout.log"
    log.write_text("MPAS finished\n", encoding="utf-8")
    report = validate_output_contract(tmp_path / "run", MpasOutputContract((Path("mpasout.nc"),), Path("stdout.log"), ("MPAS finished",)))
    assert report.is_valid


def test_jaci_pbs_renderer_preserves_explicit_argv(tmp_path: Path) -> None:
    """PBS rendering must not reintroduce implicit shell parsing."""
    request = ExecutionRequest(("mpiexec", "-n", "128", "/opt/mpas/bin/mpas_atmosphere"), tmp_path / "run", {"OMP_NUM_THREADS": "1"})
    path = render_pbs(tmp_path / "run/job.pbs", request, JaciPbsResources("pesqmidi", "00:30:00", 1, 128, 128, "mpas_test"))
    text = path.read_text(encoding="utf-8")
    assert "#PBS -q pesqmidi" in text
    assert "export OMP_NUM_THREADS=1" in text
    assert "mpiexec -n 128 /opt/mpas/bin/mpas_atmosphere" in text
