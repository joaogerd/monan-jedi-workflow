"""Interactive PBS wait presentation for the cycle-aware JEDI CLI.

This module intentionally contains presentation logic only.  It does not decide
scientific success: scheduler completion remains separate from
``jedi-validate``.  The terminal behaviour mirrors the small PBS helper used by
MPAS-BMatrix: qstat is polled at the configured interval while an in-place
braille spinner, elapsed time and next-check countdown keep an interactive
terminal visibly alive.

Redirected/non-interactive output never receives spinner control sequences.
Instead it gets persistent ``[RUN]`` lines suitable for logs and CI.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone
from typing import TextIO

from .jedi_stage import load_jedi_run
from .scheduler import PBSError, query

_SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
_ANSI = {
    "cyan": "\033[36m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "dim": "\033[2m",
    "reset": "\033[0m",
}


def _timestamp() -> str:
    """Return a normalized UTC timestamp for the JEDI submission manifest."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _color_enabled(stream: TextIO) -> bool:
    """Return whether ANSI colors should be emitted on ``stream``.

    ``MONAN_JEDI_COLOR`` accepts ``always``, ``never`` and ``auto``.  ``auto``
    is the default and enables colors only for an interactive terminal.
    ``NO_COLOR`` always wins and disables color output.
    """
    if os.environ.get("NO_COLOR") is not None:
        return False
    mode = os.environ.get("MONAN_JEDI_COLOR", "auto").strip().lower()
    if mode == "always":
        return True
    if mode == "never":
        return False
    return stream.isatty()


def _paint(text: str, color: str, stream: TextIO) -> str:
    """Apply one optional ANSI style to ``text``."""
    if not _color_enabled(stream):
        return text
    return f"{_ANSI[color]}{text}{_ANSI['reset']}"


def _format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as ``MM:SS`` or ``HH:MM:SS``."""
    total = max(0, int(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _spinner_line(
    job_id: str,
    state: str,
    elapsed: str,
    remaining: float,
    frame: str,
    stream: TextIO,
) -> str:
    """Build the concise in-place line used while a PBS job is active."""
    next_check = max(0, int(remaining))
    return (
        f"{_paint(frame, 'cyan', stream)} "
        f"PBS job {job_id}: state {_paint(state, 'yellow', stream)} "
        f"{_paint(f'elapsed {elapsed}', 'dim', stream)} "
        f"{_paint(f'next check in {next_check}s', 'dim', stream)}"
    )


def _erase_spinner_line(stream: TextIO) -> None:
    """Erase the current interactive terminal row."""
    stream.write("\r\033[2K")
    stream.flush()


def _wait_for_pbs_job(
    job_id: str,
    *,
    poll_seconds: int,
    timeout_seconds: int | None,
    stream: TextIO,
) -> str | None:
    """Wait for one PBS job while keeping scheduler polling rate unchanged.

    ``qstat`` is called only once per ``poll_seconds``.  On a TTY, the braille
    frame refreshes every 0.1 s between scheduler queries.  When output is not a
    TTY, one stable ``[RUN]`` line is emitted per scheduler query instead.
    """
    interactive = stream.isatty()
    started = time.monotonic()
    next_poll = started
    last_state: str | None = None
    frame_index = 0

    if not interactive:
        print(f"• PBS job {job_id}: waiting for completion.", file=stream, flush=True)

    while True:
        now = time.monotonic()
        elapsed_seconds = now - started

        if timeout_seconds is not None and elapsed_seconds >= timeout_seconds:
            if interactive:
                _erase_spinner_line(stream)
            raise TimeoutError(
                f"Timed out after {timeout_seconds}s waiting for JEDI job {job_id}."
            )

        if now >= next_poll:
            present, state = query(job_id)
            last_state = state or last_state
            elapsed = _format_elapsed(elapsed_seconds)

            if not present or state in {"C", "F"}:
                if interactive:
                    _erase_spinner_line(stream)
                symbol = _paint("✓", "green", stream)
                print(
                    f"{symbol} PBS job {job_id}: scheduler finished "
                    f"{_paint(f'({elapsed})', 'dim', stream)}",
                    file=stream,
                    flush=True,
                )
                return state or last_state

            next_poll = now + poll_seconds
            if not interactive:
                print(
                    f"[RUN] PBS job {job_id}: state {state or 'unknown'}; "
                    f"elapsed {elapsed}; next check in {poll_seconds}s.",
                    file=stream,
                    flush=True,
                )

        if interactive:
            current = time.monotonic()
            elapsed = _format_elapsed(current - started)
            line = _spinner_line(
                job_id,
                last_state or "checking",
                elapsed,
                next_poll - current,
                _SPINNER_FRAMES[frame_index],
                stream,
            )
            stream.write("\r\033[2K" + line)
            stream.flush()
            frame_index = (frame_index + 1) % len(_SPINNER_FRAMES)
            sleep_for = min(0.1, max(0.01, next_poll - time.monotonic()))
        else:
            sleep_for = max(0.01, next_poll - time.monotonic())

        if timeout_seconds is not None:
            deadline = started + timeout_seconds
            sleep_for = min(sleep_for, max(0.01, deadline - time.monotonic()))
        time.sleep(sleep_for)


def _read_manifest(path: Path) -> dict[str, object]:
    """Load the JEDI submission manifest with stage-oriented errors."""
    if not path.is_file():
        raise FileNotFoundError(
            "JEDI submission manifest not found. Run 'jedi-prepare' first: "
            f"{path}"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise PBSError(f"Invalid JEDI manifest: {path}") from error
    if not isinstance(payload, dict):
        raise PBSError(f"JEDI manifest must be a JSON object: {path}")
    return payload


def _write_manifest(path: Path, payload: dict[str, object]) -> None:
    """Atomically persist scheduler state without touching scientific outputs."""
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def wait_jedi(
    config_dir: Path,
    cycle_time: str,
    *,
    poll_seconds: int = 30,
    timeout_seconds: int | None = None,
    stream: TextIO | None = None,
) -> str | None:
    """Wait for JEDI PBS completion with MPAS-BMatrix-style terminal progress.

    Scheduler completion is recorded in the existing JEDI submission manifest.
    No scientific output is validated here; ``jedi-validate`` remains the
    explicit next operation.
    """
    if poll_seconds < 1:
        raise ValueError("poll_seconds must be at least 1.")
    if timeout_seconds is not None and timeout_seconds < 1:
        raise ValueError("timeout_seconds must be at least 1 when provided.")

    output = sys.stdout if stream is None else stream
    run = load_jedi_run(config_dir, cycle_time)
    manifest = _read_manifest(run.manifest_path)
    job_id = manifest.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise PBSError("JEDI run manifest has no submitted job_id.")

    state = _wait_for_pbs_job(
        job_id,
        poll_seconds=poll_seconds,
        timeout_seconds=timeout_seconds,
        stream=output,
    )
    manifest.update(
        {
            "state": "scheduler-finished",
            "scheduler_last_state": state,
            "scheduler_finished_at": _timestamp(),
        }
    )
    _write_manifest(run.manifest_path, manifest)
    return state
