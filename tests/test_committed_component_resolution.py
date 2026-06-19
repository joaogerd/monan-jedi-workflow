"""Integration test for the committed minimal cyclic experiment."""

from pathlib import Path

from monan_jedi_workflow.components import resolve_experiment_components


EXPERIMENT = (
    Path(__file__).resolve().parents[1]
    / "configs/experiments/cycle_1day_3dfgat_x1.10242.yaml"
)


def test_committed_cycle_example_resolves_all_selected_components() -> None:
    resolved = resolve_experiment_components(EXPERIMENT)
    components = resolved["components"]

    assert components["assimilation"]["assimilation"]["cost_type"] == "3D-FGAT"
    assert components["forecast"]["forecast"]["output_interval_hours"] == 3
    assert components["background"]["background"]["source"] == "previous_forecast"
    assert components["bmatrix"]["bmatrix"]["covariance_model"] == "MPASstatic"
    assert components["geometry"]["geometry"]["mesh"] == "x1.10242"
    assert components["platform"]["platform"]["scheduler"] == "PBS"
    assert components["observations"]["observations"]["instruments"] == [
        "radiosonde",
        "gnssro_ref_ncep",
        "sfc_corrected",
    ]
