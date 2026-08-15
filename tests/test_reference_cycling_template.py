from pathlib import Path

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
    rendered = template.format(**context)

    assert "begin: '2018-04-14T21:00:00Z'" in rendered
    assert "length: PT6H" in rendered
    assert "mpasout.2018-04-14_21.00.00.nc" in rendered
    assert "date: '2018-04-14T21:00:00Z'" in rendered
    assert "sondes_obs_2018041500_m.nc4" in rendered
    assert "gnssro_obs_2018041500_s.nc4" in rendered
    assert "sfc_obs_2018041500_m.nc4" in rendered
    assert "covariance model: MPASstatic" in rendered
    assert "cost type: 3D-FGAT" in rendered
