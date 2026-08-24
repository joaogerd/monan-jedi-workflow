from pathlib import Path

import pytest
import yaml

from monan_jedi_workflow.analysis_cycle import analysis_cycle_context
from monan_jedi_workflow.cycle_context import parse_cycle_time


def test_reference_template_preserves_baseline_cycle_semantics() -> None:
    root = Path(__file__).resolve().parents[1]
    template = (
        root
        / "examples/simpleworkflow/cycled_da/templates/variational.baseline_passed.yaml.in"
    ).read_text(encoding="utf-8")

    context = analysis_cycle_context(
        parse_cycle_time("2018-04-15T00:00:00Z"),
        step_hours=6,
        background_offset_hours=-3,
        window_hours=6,
    )
    context["run_dir"] = "/runtime/2018041500"
    context["model_tstep"] = "PT20M"
    rendered = template.format(**context)

    assert "begin: '2018-04-14T21:00:00Z'" in rendered
    assert "length: PT6H" in rendered
    assert "mpasout.2018-04-14_21.00.00.nc" in rendered
    assert "date: '2018-04-15T00:00:00Z'" in rendered
    assert "sondes_obs_2018041500_m.nc4" in rendered
    assert "gnssro_obs_2018041500_s.nc4" in rendered
    assert "sfc_obs_2018041500_m.nc4" in rendered
    assert "covariance model: MPASstatic" in rendered
    assert "cost type: 3D-FGAT" in rendered
    assert "tstep: PT20M" in rendered


@pytest.mark.parametrize(
    ("cycle", "logical_date"),
    [
        ("2018-04-15T00:00:00Z", "2018-04-15T00:00:00Z"),
        ("2018-04-15T06:00:00Z", "2018-04-15T06:00:00Z"),
        ("2018-04-15T12:00:00Z", "2018-04-15T12:00:00Z"),
    ],
)
def test_static_b_path_has_cycle_aware_logical_time(
    cycle: str, logical_date: str
) -> None:
    root = Path(__file__).resolve().parents[1]
    template = (
        root
        / "examples/simpleworkflow/cycled_da/templates/variational.baseline_passed.yaml.in"
    ).read_text(encoding="utf-8")
    context = analysis_cycle_context(
        parse_cycle_time(cycle),
        step_hours=6,
        background_offset_hours=-3,
        window_hours=6,
    )
    context["run_dir"] = "/runtime"
    context["model_tstep"] = "PT20M"
    rendered = yaml.safe_load(template.format(**context))

    covariance = rendered["cost function"]["background error"]
    assert covariance["date"] == logical_date
    assert covariance["covariance model"] == "MPASstatic"

    case = yaml.safe_load(
        (root / "examples/simpleworkflow/cycled_da/jedi.yaml.example").read_text()
    )
    assert case["jedi"]["links"][0]["source"] == "{bmatrix_root}"


def test_reference_observers_explicitly_use_nearest_time_interpolation() -> None:
    root = Path(__file__).resolve().parents[1]
    template = (
        root
        / "examples/simpleworkflow/cycled_da/templates/variational.baseline_passed.yaml.in"
    ).read_text(encoding="utf-8")
    context = analysis_cycle_context(
        parse_cycle_time("2018-04-15T06:00:00Z"),
        step_hours=6,
        background_offset_hours=-3,
        window_hours=6,
    )
    context.update({"run_dir": "/runtime", "model_tstep": "PT20M"})
    rendered = yaml.safe_load(template.format(**context))
    observers = rendered["cost function"]["observations"]["observers"]
    assert [item["obs space"]["name"] for item in observers] == [
        "Radiosonde",
        "GnssroRefNCEP",
        "SfcCorrected",
    ]
    assert all(
        item["get values"]["time interpolation"] == "nearest"
        for item in observers
    )


def test_x1_10242_jedi_namelist_has_validated_scientific_parameters() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / (
        "examples/simpleworkflow/cycled_da/templates/"
        "namelist.atmosphere.jedi-x1.10242.in"
    )
    content = path.read_text(encoding="utf-8")
    assert "config_dt = 1200.0" in content
    assert "config_len_disp = 240000.0" in content
    assert "config_o3climatology = .true." in content
    assert "config_physics_suite = 'mesoscale_reference'" in content
    assert "config_horiz_mixing = '2d_smagorinsky'" in content
    assert "config_visc4_2dsmag = 0.05" in content
    assert "namelists/480km" not in content
