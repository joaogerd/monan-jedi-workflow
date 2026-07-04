"""Reusable foreground progress reporting for long-running execution backends.

The reporter is scheduler-neutral: PBS, Slurm, local process pools, or any
future backend can emit the same submission, state, heartbeat, and completion
events. Terminal animation is deliberately a presentation concern and never a
signal of scientific success.
"""

from __future__ import annotations

import sys
import threading
from typing import Protocol, TextIO


class JobProgressReporter(Protocol):
    """Report generic lifecycle progress for a submitted background job."""

    def submitted(self, *, backend: str, identifier: str, label: str) -> None:
        """Report that a backend accepted a job submission."""

    def state(self, *, backend: str, identifier: str, state: str) -> None:
        """Report an observed backend state transition."""

    def heartbeat(self, *, backend: str, identifier: str, state: str, elapsed_seconds: int) -> None:
        """Report that a job remains in an unchanged state."""

    def completed(
        self,
        *,
        backend: str,
        identifier: str,
        terminal_state: str | None,
        elapsed_seconds: int,
    ) -> None:
        """Report that backend-level waiting completed."""


class NullJobProgressReporter:
    """Discard generic job-progress events.

    Useful for embedding the workflow in another application that owns its own
    user interface, or for tests that need no terminal output.
    """

    def submitted(self, *, backend: str, identifier: str, label: str) -> None:
        """Discard the submission event."""

    def state(self, *, backend: str, identifier: str, state: str) -> None:
        """Discard the state-transition event."""

    def heartbeat(self, *, backend: str, identifier: str, state: str, elapsed_seconds: int) -> None:
        """Discard the heartbeat event."""

    def completed(
        self,
        *,
        backend: str,
        identifier: str,
        terminal_state: str | None,
        elapsed_seconds: int,
    ) -> None:
        """Discard the completion event."""


class TerminalJobProgressReporter:
    """Render generic job progress as text plus an optional braille spinner.

    Text status lines are always emitted to preserve an audit trail. The braille
    spinner is enabled only for an interactive TTY by default, so redirected
    output, CI logs, and text files remain plain and machine-readable.
    """

    _FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

    def __init__(
        self,
        *,
        stream: TextIO | None = None,
        spinner_interval_seconds: float = 0.1,
        spinner_enabled: bool | None = None,
    ) -> None:
        if spinner_interval_seconds <= 0:
            raise ValueError("spinner_interval_seconds must be positive.")
        self.stream = sys.stdout if stream is None else stream
        self.spinner_interval_seconds = spinner_interval_seconds
        self.spinner_enabled = self.stream.isatty() if spinner_enabled is None else spinner_enabled
        self._lock = threading.RLock()
        self._stop_event: threading.Event | None = None
        self._thread: threading.Thread | None = None
        self._spinner_text = ""

    @staticmethod
    def _prefix(backend: str) -> str:
        """Normalize a backend display label for terminal output."""
        return f"[{backend}]"

    def _write_line(self, text: str) -> None:
        """Write one stable text line after clearing any active spinner."""
        self._stop_spinner()
        with self._lock:
            self.stream.write(f"{text}\n")
            self.stream.flush()

    def _start_spinner(self, *, backend: str, identifier: str, state: str) -> None:
        """Start an in-place braille spinner for the current generic wait state."""
        if not self.spinner_enabled:
            return
        self._stop_spinner()
        event = threading.Event()
        self._stop_event = event

        def spin() -> None:
            index = 0
            while not event.is_set():
                text = f"{self._FRAMES[index]} {self._prefix(backend)} {identifier} state={state}; waiting..."
                with self._lock:
                    self._spinner_text = text
                    self.stream.write(f"\r{text}")
                    self.stream.flush()
                index = (index + 1) % len(self._FRAMES)
                event.wait(self.spinner_interval_seconds)

        self._thread = threading.Thread(
            target=spin,
            name="monan-jedi-job-progress",
            daemon=True,
        )
        self._thread.start()

    def _stop_spinner(self) -> None:
        """Stop and erase the active spinner without emitting a status line."""
        event, thread = self._stop_event, self._thread
        if event is None:
            return
        event.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join()
        with self._lock:
            if self._spinner_text:
                self.stream.write(f"\r{' ' * len(self._spinner_text)}\r")
                self.stream.flush()
            self._spinner_text = ""
            self._stop_event = None
            self._thread = None

    def submitted(self, *, backend: str, identifier: str, label: str) -> None:
        """Render a generic submitted-job message."""
        self._write_line(
            f"{self._prefix(backend)} submitted {identifier} ({label}); waiting for scheduler completion."
        )

    def state(self, *, backend: str, identifier: str, state: str) -> None:
        """Render an observed state transition and begin spinner animation."""
        self._write_line(f"{self._prefix(backend)} {identifier} state={state}; still waiting.")
        self._start_spinner(backend=backend, identifier=identifier, state=state)

    def heartbeat(self, *, backend: str, identifier: str, state: str, elapsed_seconds: int) -> None:
        """Render a periodic unchanged-state heartbeat and resume animation."""
        self._write_line(
            f"{self._prefix(backend)} {identifier} still state={state} after {elapsed_seconds}s."
        )
        self._start_spinner(backend=backend, identifier=identifier, state=state)

    def completed(
        self,
        *,
        backend: str,
        identifier: str,
        terminal_state: str | None,
        elapsed_seconds: int,
    ) -> None:
        """Render completion of backend-level waiting and clear the spinner."""
        suffix = f"state={terminal_state}" if terminal_state is not None else "left qstat"
        self._write_line(
            f"{self._prefix(backend)} {identifier} {suffix} after {elapsed_seconds}s; "
            "scheduler wait completed."
        )

    def close(self) -> None:
        """Stop an active spinner when a caller abandons waiting early."""
        self._stop_spinner()
