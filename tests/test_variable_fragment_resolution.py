from pathlib import Path

from monan_jedi_workflow.config import load_experiment_config, validate_experiment_config
from monan_jedi_workflow.fragments import resolve_variable_config


EXPERIMENT_DIR = Path("configs/experiments/3dfgat_mpastatic_x1.10242_2018041500")


def test_variable_selector_resolves_mpas_3dfgat_core_fragment():
    resolved = resolve_variable_config(
        EXPERIMENT_DIR,
        {"variables": {"use": "mpas_3dfgat_core"}},
    )

    assert len(resolved["analysis_variables"]) == 5
    assert len(resolved["model_variables"]) == 30
    assert len(resolved["background_state_variables"]) == 30
    assert resolved["model_variables"] == resolved["background_state_variables"]


def test_loaded_baseline_config_with_variable_fragment_still_validates():
    config = load_experiment_config(EXPERIMENT_DIR)

    messages = validate_experiment_config(config)

    assert "configuration contract: OK" in messages
