from pathlib import Path

from monan_jedi_workflow import cli


def test_cycle_stage_commands_require_cycle_time() -> None:
    parser = cli.build_parser()
    args = parser.parse_args([
        "mpas-submit", "configs/example", "--cycle", "2018-04-15T00:00:00Z", "--wait"
    ])
    assert args.command == "mpas-submit"
    assert args.config_dir == Path("configs/example")
    assert args.cycle == "2018-04-15T00:00:00Z"
    assert args.wait is True

    args = parser.parse_args([
        "obs2ioda-run", "configs/example", "--cycle", "2018-04-15T00:00:00Z"
    ])
    assert args.command == "obs2ioda-run"
    assert args.force is False
