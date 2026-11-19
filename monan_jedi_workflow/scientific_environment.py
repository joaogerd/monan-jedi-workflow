"""Shared scientific PBS environment rendering for native stage applications.

Reuses the pre-existing site profile/installed runtime contract rather than
guessing one-off library paths. Python runs on LOGIN to render this shell text.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .site import render_site_environment_block


def render_native_site_setup(pbs: dict[str, Any], *, config_dir: Path) -> list[str]:
    """Return native shell statements for the configured HPC site profile.

    All stages use the same mechanism. A missing optional site profile retains
    legacy stage behavior for existing experiments; maintained generated
    experiments always declare one. Never run Python in the PBS job.
    """
    reference = pbs.get("site_config")
    if reference is None:
        return []
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError("pbs.site_config must be a nonempty site YAML path")
    site_path = Path(reference).expanduser()
    if not site_path.is_absolute():
        site_path = Path(config_dir) / site_path
    site_path = site_path.resolve()
    if not site_path.is_file():
        raise FileNotFoundError(
            f"Scientific PBS site profile not found: {site_path}. "
            "Configure pbs.site_config with a valid site YAML."
        )
    try:
        return render_site_environment_block(site_path).splitlines()
    except (ValueError, KeyError, OSError) as error:
        raise ValueError(
            f"Failed to render native scientific PBS environment from {site_path}: {error}"
        ) from error
