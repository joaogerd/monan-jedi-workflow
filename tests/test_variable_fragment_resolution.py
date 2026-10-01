from pathlib import Path

from monan_jedi_workflow.fragments import resolve_variable_config


EXPERIMENT_DIR = Path("configs/experiments/template")


def test_variable_selector_resolves_mpas_3dfgat_core_fragment():
    resolved = resolve_variable_config(
        EXPERIMENT_DIR,
        {"variables": {"use": "mpas_3dfgat_core"}},
    )

    assert len(resolved["analysis_variables"]) == 5
    assert len(resolved["model_variables"]) == 30
    assert len(resolved["background_state_variables"]) == 30
    assert resolved["model_variables"] == resolved["background_state_variables"]


