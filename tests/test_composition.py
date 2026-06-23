"""Tests for in-memory component composition."""

from pathlib import Path

from monan_jedi_workflow.composition import compose_cyclic_experiment


EXPERIMENT = (
    Path(__file__).resolve().parents[1]
    / "configs/experiments/cycle_1day_3dfgat_x1.10242.yaml"
)


def test_committed_cycle_composes_component_defaults_and_overrides() -> None:
    effective = compose_cyclic_experiment(EXPERIMENT)

    assert effective["assimilation"]["method"] == "3dvar_fgat"
    assert effective["assimilation"]["outer_loops"] == 2
    assert effective["assimilation"]["inner_iterations"] == 10
    assert effective["assimilation"]["fgat"]["trajectory_offsets_hours"] == [-3, 0, 3]
    assert effective["forecast"]["output_interval_hours"] == 3
    assert effective["background"]["source"] == "previous_forecast"
    assert effective["bmatrix"]["covariance_model"] == "MPASstatic"
    assert effective["geometry"]["partition_file"] == "x1.10242.graph.info.part.64"
    assert effective["observations"]["instruments"] == [
        "radiosonde",
        "gnssro_ref_ncep",
        "sfc_corrected",
    ]
    assert effective["run"]["tasks"] == 64
    assert effective["run"]["walltime"] == "00:30:00"
    assert effective["site"]["scheduler"] == "PBS"
    assert effective["installation"]["bin_root"].endswith("/bin")
    assert effective["jedi"]["variational"].endswith("/mpasjedi_variational.x")
    assert effective["model"]["atmosphere"].endswith("/mpas_atmosphere")
