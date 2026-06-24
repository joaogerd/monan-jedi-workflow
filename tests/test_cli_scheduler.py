from pathlib import Path

from monan_jedi_workflow import cli


def test_submit_accepts_wait_before_config_directory() -> None:
    args = cli.build_parser().parse_args(["submit", "--wait", "configs/example"])
    assert args.command == "submit"
    assert args.wait is True
    assert args.config_dir == Path("configs/example")


def test_wait_and_validate_run_are_public_commands() -> None:
    assert cli.build_parser().parse_args(["wait", "configs/example"]).command == "wait"
    assert cli.build_parser().parse_args(["validate-run", "configs/example"]).command == "validate-run"
