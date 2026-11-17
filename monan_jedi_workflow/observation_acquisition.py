"""Acquire missing exact-cycle observation files before native Obs2IODA prepare.

Provider URLs are declared in the observation-domain YAML. This module never
guesses historical archive URLs or substitutes files from another cycle.
"""
from __future__ import annotations

from pathlib import Path
import tempfile

from .input_acquisition import ensure_input, InputUnavailable
from .stage_config import render_text


def acquire_required_observations(op, request) -> list[Path]:
    """Ensure raw files required by this cycle are available on the login node.

    Only the declared converter input files are considered; executable scripts
    and libraries are not downloadable data. Providers are matched by the
    converter name in obs2ioda.acquisition.providers.
    """
    from .platform_backend import materialize, render_run
    from .obs2ioda_stage import _build_plan

    config = op.section.get("acquisition", {})
    if not isinstance(config, dict):
        raise ValueError("obs2ioda.acquisition must be a mapping")
    providers = config.get("providers", [])
    if not isinstance(providers, list):
        raise ValueError("obs2ioda.acquisition.providers must be a list")
    names = {}
    for provider in providers:
        if not isinstance(provider, dict) or not isinstance(provider.get("converter"), str):
            raise ValueError("Each Obs acquisition provider needs a converter name")
        name = provider["converter"]
        if name in names:
            raise ValueError(f"duplicate acquisition provider: {name}")
        names[name] = provider
    acquired = []
    with tempfile.TemporaryDirectory(prefix="monan-obs-acquisition-") as temporary:
        directory = materialize(op, Path(temporary))
        run = render_run(op, request, directory)
        plan = _build_plan(run)
        for converter in plan["converters"]:
            name = converter["name"]
            for source in converter["inputs"]:
                path = Path(source)
                # Only raw observation files, not tools, runners or templates.
                if not (path.name.endswith(".bufr") or path.name.endswith(".nr")):
                    continue
                if path.is_file() and path.stat().st_size > 0:
                    continue
                provider = names.get(name)
                if not provider:
                    raise InputUnavailable(
                        f"Observations for {request.cycle} unavailable: {path}. "
                        f"No URL provider configured for converter '{name}'. "
                        "Configure obs2ioda.acquisition.providers or obtain "
                        "the exact-cycle raw files from a verified archive."
                    )
                url = render_text(
                    provider.get("url"),
                    run.context,
                    label=f"obs2ioda.acquisition.providers.{name}.url",
                )
                acquired.append(ensure_input(
                    target=path,
                    url=url,
                    label=f"{name} {request.cycle}",
                    timeout=int(provider.get("timeout_seconds", 300)),
                    magic=b"BUFR" if provider.get("validate_bufr", False) else None,
                ))
    return acquired
