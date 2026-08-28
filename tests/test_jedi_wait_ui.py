from __future__ import annotations

import io

from monan_jedi_workflow import cli
from monan_jedi_workflow import jedi_wait_ui


class _TTY(io.StringIO):
    def isatty(self) -> bool:
        return True


class _Log(io.StringIO):
    def isatty(self) -> bool:
        return False


def _fake_clock(monkeypatch):
    now = [0.0]

    def monotonic() -> float:
        return now[0]

    def sleep(seconds: float) -> None:
        now[0] += seconds

    monkeypatch.setattr(jedi_wait_ui.time, "monotonic", monotonic)
    monkeypatch.setattr(jedi_wait_ui.time, "sleep", sleep)
    return now


def test_format_elapsed_matches_mpas_tools_style() -> None:
    assert jedi_wait_ui._format_elapsed(0) == "00:00"
    assert jedi_wait_ui._format_elapsed(65) == "01:05"
    assert jedi_wait_ui._format_elapsed(3661) == "01:01:01"


def test_interactive_wait_uses_in_place_braille_spinner(monkeypatch) -> None:
    _fake_clock(monkeypatch)
    states = iter(((True, "R"), (False, None)))
    monkeypatch.setattr(jedi_wait_ui, "query", lambda _job_id: next(states))
    monkeypatch.setenv("NO_COLOR", "1")

    stream = _TTY()
    state = jedi_wait_ui._wait_for_pbs_job(
        "363911.pbs-ha",
        poll_seconds=1,
        timeout_seconds=10,
        stream=stream,
    )

    output = stream.getvalue()
    assert state == "R"
    assert "⠋" in output or "⠙" in output
    assert "PBS job 363911.pbs-ha: state R" in output
    assert "elapsed 00:" in output
    assert "next check in" in output
    # Spinner refreshes with carriage returns rather than one persistent line per frame.
    assert "\r\033[2K" in output
    assert output.count("scheduler finished") == 1


def test_noninteractive_wait_keeps_logs_plain(monkeypatch) -> None:
    _fake_clock(monkeypatch)
    states = iter(((True, "Q"), (True, "R"), (False, None)))
    monkeypatch.setattr(jedi_wait_ui, "query", lambda _job_id: next(states))

    stream = _Log()
    state = jedi_wait_ui._wait_for_pbs_job(
        "363911.pbs-ha",
        poll_seconds=1,
        timeout_seconds=10,
        stream=stream,
    )

    output = stream.getvalue()
    assert state == "R"
    assert "[RUN] PBS job 363911.pbs-ha: state Q" in output
    assert "[RUN] PBS job 363911.pbs-ha: state R" in output
    assert "⠋" not in output
    assert "\033[2K" not in output


def test_jedi_submit_wait_uses_terminal_waiter(monkeypatch, tmp_path) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_submit(_config_dir, _cycle, **kwargs):
        calls.append(("submit", kwargs))
        return "363911.pbs-ha"

    def fake_wait(_config_dir, _cycle, **kwargs):
        calls.append(("wait", kwargs))
        return "R"

    monkeypatch.setattr(cli, "submit_jedi", fake_submit)
    monkeypatch.setattr(cli, "wait_jedi", fake_wait)

    result = cli.main(
        [
            "jedi-submit",
            str(tmp_path),
            "--cycle",
            "2018-04-15T00:00:00Z",
            "--wait",
            "--poll-seconds",
            "17",
        ]
    )

    assert result == 0
    assert calls[0][0] == "submit"
    assert calls[0][1]["wait"] is False
    assert calls[1] == (
        "wait",
        {"poll_seconds": 17, "timeout_seconds": None},
    )
