"""Optional declarative refinements applied after the base MPAS staging step."""

from __future__ import annotations

from pathlib import Path

from .mpas_render import patch_namelist, patch_streams
from .mpas_stage import MPASRun
from .mpas_stage import prepare_mpas as _prepare_mpas


def prepare_mpas(config_dir: Path, cycle_time: str) -> MPASRun:
    """Prepare one MPAS run and apply optional namelist/streams overrides.

    The core stage continues to own links, template rendering, PBS generation
    and the run manifest. These extensions only modify files that have already
    been rendered in the cycle work directory.
    """
    run = _prepare_mpas(config_dir, cycle_time)

    replacements = run.config.get("namelist_replacements")
    if replacements is not None:
        target = run.config.get("namelist_target", "namelist.atmosphere")
        patch_namelist(run.run_dir / str(target), replacements, run.context)

    stream_overrides = run.config.get("stream_overrides")
    if stream_overrides is not None:
        target = run.config.get("streams_target", "streams.atmosphere")
        patch_streams(run.run_dir / str(target), stream_overrides, run.context)

    return run
