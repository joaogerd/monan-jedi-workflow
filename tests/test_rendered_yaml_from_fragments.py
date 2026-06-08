from pathlib import Path

from monan_jedi_workflow.config import load_experiment_config
from monan_jedi_workflow.render import render_yaml


EXPERIMENT_DIR = Path("configs/experiments/3dfgat_mpastatic_x1.10242_2018041500")


def test_rendered_yaml_contains_fragmented_observers_in_order():
    config = load_experiment_config(EXPERIMENT_DIR)

    rendered = render_yaml(config)

    radiosonde = rendered.index("name: Radiosonde")
    gnssro = rendered.index("name: GnssroRefNCEP")
    sfc = rendered.index("name: SfcCorrected")

    assert radiosonde < gnssro < sfc


def test_rendered_yaml_preserves_baseline_observer_outputs():
    config = load_experiment_config(EXPERIMENT_DIR)

    rendered = render_yaml(config)

    assert "obsout_3dfgat_sondes.nc4" in rendered
    assert "obsout_3dfgat_gnssroref.nc4" in rendered
    assert "obsout_3dfgat_sfc.nc4" in rendered


def test_rendered_yaml_preserves_baseline_observation_operators():
    config = load_experiment_config(EXPERIMENT_DIR)

    rendered = render_yaml(config)

    assert "name: VertInterp" in rendered
    assert "name: GnssroRefNCEP" in rendered
    assert "name: SfcCorrected" in rendered
    assert "linear obs operator:" in rendered
    assert "name: Identity" in rendered
