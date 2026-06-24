from monan_jedi_workflow.cycle_context import parse_cycle_time


def test_cycle_context_renders_mpas_and_valid_time() -> None:
    cycle = parse_cycle_time("2018-04-15T00:00:00Z")
    context = cycle.render_context(lead_hours=6)
    assert context["cycle_id"] == "20180415T000000Z"
    assert context["mpas_time"] == "2018-04-15_00:00:00"
    assert context["valid_id"] == "20180415T060000Z"
    assert context["mpas_valid_time"] == "2018-04-15_06:00:00"
