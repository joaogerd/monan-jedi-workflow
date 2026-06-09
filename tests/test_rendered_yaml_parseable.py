from pathlib import Path

import yaml

from monan_jedi_workflow.config import load_experiment_config
from monan_jedi_workflow.render import render_yaml


EXPERIMENT_DIR = Path("configs/experiments/3dfgat_mpastatic_x1.10242_2018041500")


def test_rendered_yaml_is_parseable_with_expected_top_level_sections():
    config = load_experiment_config(EXPERIMENT_DIR)

    document = yaml.safe_load(render_yaml(config))

    assert isinstance(document, dict)
    assert "cost function" in document
    assert "output" in document
    assert "variational" in document


def test_rendered_yaml_preserves_core_mpas_jedi_structure():
    config = load_experiment_config(EXPERIMENT_DIR)

    document = yaml.safe_load(render_yaml(config))
    cost_function = document["cost function"]
    observers = cost_function["observations"]["observers"]

    assert cost_function["cost type"] == "3D-FGAT"
    assert cost_function["model"]["name"] == "MPAS"
    assert len(cost_function["model"]["model variables"]) == 30
    assert len(cost_function["analysis variables"]) == 5
    assert [item["obs space"]["name"] for item in observers] == [
        "Radiosonde",
        "GnssroRefNCEP",
        "SfcCorrected",
    ]
