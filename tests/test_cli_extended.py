from pathlib import Path

from monan_jedi_workflow.cli_extended import _parser


def test_new_cycle_stage_commands_accept_cycle_arguments() -> None:
    parser = _parser()

    wps = parser.parse_args([
        "wps-run", "cases/example", "--cycle", "2026-06-26T00:00:00Z", "--force"
    ])
    assert wps.command == "wps-run"
    assert wps.config_dir == Path("cases/example")
    assert wps.force is True

    init = parser.parse_args([
        "mpas-init-submit", "cases/example", "--cycle", "2026-06-26T00:00:00Z", "--wait"
    ])
    assert init.command == "mpas-init-submit"
    assert init.wait is True
