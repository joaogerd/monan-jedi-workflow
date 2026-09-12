"""Temporal model for analysis-centred MONAN-JEDI cycling.

This module is the single owner of time arithmetic used by a deterministic
analysis cycle.  It deliberately contains no scheduler, filesystem, MPAS or
JEDI execution logic.

Why this module exists
----------------------
Earlier workflow prototypes represented several different timestamps with the
word ``cycle``.  In 3D-FGAT that is dangerous because the analysis time, the
background valid time, the assimilation-window bounds, the previous/next
analysis and the next required background may all be different.

The public convention adopted by this project is:

``cycle_time == analysis_time`` for the JEDI analysis stage.

All other timestamps are derived from explicit configuration values.  The
reference baseline currently being reconstructed uses a 6-hour analysis step,
a background 3 hours before the analysis, and a 6-hour FGAT window.  Those
values are examples, not hard-coded scientific assumptions.

Keeping the arithmetic here also protects orchestrator independence.  A
simpleWorkflow, ecFlow or Cylc definition should consume already-defined stage
contracts; it should not need to duplicate scientific date arithmetic.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .cycle_context import CycleContext
from .stage_config import StageConfigurationError


def _iso(value: datetime) -> str:
    """Return one timezone-aware timestamp in normalized UTC ISO-8601 form."""
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _time_fields(prefix: str, value: datetime) -> dict[str, str]:
    """Build all supported template representations for one logical time.

    Parameters
    ----------
    prefix
        Semantic name used by templates, for example ``analysis`` or
        ``background``.
    value
        Time to expose.  It is normalized to UTC before formatting.

    Returns
    -------
    dict[str, str]
        Template fields using ISO-8601, compact ``YYYYMMDDHH`` and MPAS file
        conventions.

    Notes
    -----
    MPAS runtime files appear in two common timestamp forms: one using colons
    (``YYYY-MM-DD_HH:MM:SS``) and one using periods in filenames
    (``YYYY-MM-DD_HH.MM.SS``).  Both are exposed so templates do not need to
    perform string manipulation.
    """
    value = value.astimezone(timezone.utc)
    return {
        f"{prefix}_time": _iso(value),
        f"{prefix}_id": value.strftime("%Y%m%dT%H%M%SZ"),
        f"{prefix}_yyyymmddhh": value.strftime("%Y%m%d%H"),
        f"{prefix}_year": value.strftime("%Y"),
        f"{prefix}_month": value.strftime("%m"),
        f"{prefix}_day": value.strftime("%d"),
        f"{prefix}_hour": value.strftime("%H"),
        f"{prefix}_mpas_time": value.strftime("%Y-%m-%d_%H:%M:%S"),
        f"{prefix}_mpas_file_time": value.strftime("%Y-%m-%d_%H.%M.%S"),
    }


def analysis_cycle_context(
    cycle: CycleContext,
    *,
    step_hours: int,
    background_offset_hours: int,
    window_hours: int,
) -> dict[str, str]:
    """Return the template context for one analysis-centred DA cycle.

    Parameters
    ----------
    cycle
        Normalized cycle context.  For this function, its value is *always* the
        analysis time.
    step_hours
        Interval between consecutive analyses.  It controls
        ``previous_cycle`` and ``next_cycle`` only.
    background_offset_hours
        Offset from the analysis time to the background valid time.  Negative
        values place the background before the analysis; the reference
        3D-FGAT case uses ``-3``.
    window_hours
        Assimilation-window duration.  The current reference convention starts
        the window at the background time.

    Returns
    -------
    dict[str, str]
        Standard ``CycleContext`` fields plus semantic groups for ``analysis``,
        ``previous_cycle``, ``next_cycle``, ``background``,
        ``next_background``, ``window_begin`` and ``window_end``.

    Raises
    ------
    StageConfigurationError
        If a positive duration is non-integer/non-positive or if the background
        offset is not an integer.

    Invariants
    ----------
    - ``analysis_time == cycle.cycle_time``.
    - ``previous_cycle = analysis - step_hours``.
    - ``next_cycle = analysis + step_hours``.
    - ``background = analysis + background_offset_hours``.
    - ``next_background = next_cycle + background_offset_hours``.
    - no relationship is inferred between ``step_hours`` and
      ``background_offset_hours``.

    Notes
    -----
    The distinction between cycling interval and background offset is
    intentional.  Deriving one from the other would make the workflow silently
    wrong for FGAT configurations whose first-guess state is not valid exactly
    one cycle interval before the analysis.
    """
    for value, label in (
        (step_hours, "step_hours"),
        (window_hours, "window_hours"),
    ):
        if not isinstance(value, int) or value < 1:
            raise StageConfigurationError(
                f"jedi.cycle.{label} must be a positive integer."
            )

    if not isinstance(background_offset_hours, int):
        raise StageConfigurationError(
            "jedi.cycle.background_offset_hours must be an integer."
        )

    analysis = cycle.value
    previous_cycle = analysis - timedelta(hours=step_hours)
    next_cycle = analysis + timedelta(hours=step_hours)
    background = analysis + timedelta(hours=background_offset_hours)
    next_background = next_cycle + timedelta(hours=background_offset_hours)
    window_begin = background
    window_end = window_begin + timedelta(hours=window_hours)

    context = dict(cycle.render_context())
    for prefix, value in (
        ("analysis", analysis),
        ("previous_cycle", previous_cycle),
        ("next_cycle", next_cycle),
        ("background", background),
        ("next_background", next_background),
        ("window_begin", window_begin),
        ("window_end", window_end),
    ):
        context.update(_time_fields(prefix, value))

    context.update(
        {
            "cycle_step_hours": str(step_hours),
            "background_offset_hours": str(background_offset_hours),
            "window_hours": str(window_hours),
            "window_length": f"PT{window_hours}H",
        }
    )
    return context
