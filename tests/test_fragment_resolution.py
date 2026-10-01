from pathlib import Path

from monan_jedi_workflow.fragments import resolve_observation_config


EXPERIMENT_DIR = Path("configs/experiments/template")


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


