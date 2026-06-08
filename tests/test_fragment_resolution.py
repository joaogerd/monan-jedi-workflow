from pathlib import Path

from monan_jedi_workflow.config import load_experiment_config, validate_experiment_config
from monan_jedi_workflow.fragments import resolve_observation_config


EXPERIMENT_DIR = Path("configs/experiments/3dfgat_mpastatic_x1.10242_2018041500")


def test_baseline_observation_selector_resolves_expected_observers():
    observations = {
        "observations": {
            "use": [
                "radiosonde",
                "gnssro_ref_ncep",
                "sfc_corrected",
            ]
        }
    }

    resolved = resolve_observation_config(EXPERIMENT_DIR, observations)

    assert [observer["name"] for observer in resolved["observers"]] == [
        "Radiosonde",
        "GnssroRefNCEP",
        "SfcCorrected",
    ]


def test_loaded_baseline_config_resolves_fragmented_observations():
    config = load_experiment_config(EXPERIMENT_DIR)

    assert [observer["name"] for observer in config.observations["observers"]] == [
        "Radiosonde",
        "GnssroRefNCEP",
        "SfcCorrected",
    ]


def test_loaded_baseline_config_still_satisfies_validation_contract():
    config = load_experiment_config(EXPERIMENT_DIR)

    messages = validate_experiment_config(config)

    assert "configuration contract: OK" in messages
