"""On-demand exact-cycle observation acquisition via the proven GDEX adapter.

The legacy GDEX downloader already supports HTTPS, host TLS fallback, and
extracting a BUFR member from the daily GNSS-RO TAR.GZ archive. Reuse it.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import fcntl
import tempfile

from .input_acquisition import InputUnavailable
from .obs_cycle_inputs import cycle_candidate, find_local_cycle_input


# Restored from examples/case/profile.yaml on feature/2025-reference-case.
# The historical archive may not cover every requested date; 404 must remain
# a clear error, never an invitation to substitute data from another cycle.
GDEX_PROVIDERS = {
    "prepbufr-conventional": {
        "type": "https",
        "url": (
            "https://data.gdex.ucar.edu/d337000/prepnr/{cycle_year}/"
            "prepbufr.gdas.{cycle_yyyymmddhh}.nr"
        ),
        "product": "PREPNR",
        "timeout_seconds": 300,
    },
    "gpsro-gnssro": {
        "type": "https-tar",
        "url": (
            "https://data.gdex.ucar.edu/d735000/gpsro/{cycle_year}/"
            "gpsro.{cycle_year}{cycle_month}{cycle_day}.tar.gz"
        ),
        "member": (
            "gdas.gpsro.t{cycle_hour}z."
            "{cycle_year}{cycle_month}{cycle_day}.bufr"
        ),
        "timeout_seconds": 300,
    },
}


def _default_provider(converter: str, cycle):
    """Historical GDEX layout differs across years.

    Before 2025, PREPNR is distributed as daily TARs. Use the explicit,
    cycle-matched PREP48H product for this portability test, never a
    different cycle. The source URL/provenance marks the product difference.
    """
    if converter == "prepbufr-conventional" and cycle.value.year < 2025:
        return {
            "type": "https",
            "url": (
                "https://data.gdex.ucar.edu/d337000/prep48h/{cycle_year}/"
                "prepbufr.gdas.{cycle_year}{cycle_month}{cycle_day}."
                "t{cycle_hour}z.nr.48h"
            ),
            "product": "PREP48H",
            "timeout_seconds": 300,
        }
    return GDEX_PROVIDERS.get(converter)



@contextmanager
def _target_lock(target: Path):
    """Serialize competing acquisition attempts for one raw observation."""
    target.parent.mkdir(parents=True, exist_ok=True)
    guard = target.with_name(target.name + ".acquisition.lock")
    with guard.open("a+b") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def acquire_required_observations(op, request) -> list[Path]:
    """Fetch only missing exact-cycle raw input files before Obs2IODA prepare.

    An empty provider list in an old generated experiment means use the
    compatible GDEX defaults; explicitly setting enabled=false disables it.
    The downloaded path remains the same declared converter input.
    """
    from .platform_backend import materialize, render_run
    from .obs2ioda_stage import _build_plan
    from .obs_acquisition import _acquire_remote

    config = op.section.get("acquisition", {})
    if not isinstance(config, dict):
        raise ValueError("obs2ioda.acquisition must be a mapping")
    if config.get("enabled", True) is False:
        providers = {}
    else:
        declared = config.get("providers", [])
        if isinstance(declared, list):
            providers = {}
            for item in declared:
                if not isinstance(item, dict) or not item.get("converter"):
                    raise ValueError("Observation provider must have converter name")
                key = item["converter"]
                if key in providers:
                    raise ValueError(f"Duplicate observation provider: {key}")
                providers[key] = item
        elif isinstance(declared, dict):
            providers = declared
        else:
            raise ValueError("obs2ioda.acquisition.providers must be list or mapping")
        # Archive defaults preserve the early JACI GDEX acquisition behavior;
        # experiment-specific providers can override or disable the defaults.
        # Resolver picks the actual historical archive format by cycle.

    acquired = []
    with tempfile.TemporaryDirectory(prefix="monan-obs-acquisition-") as temporary:
        directory = materialize(op, Path(temporary))
        run = render_run(op, request, directory)
        plan = _build_plan(run)
        for converter in plan["converters"]:
            name = converter["name"]
            for source in converter["inputs"]:
                configured = Path(source)
                # Never treat runners/tools as scientific downloadable data.
                if not (configured.name.endswith(".bufr") or configured.name.endswith(".nr")):
                    continue
                candidate, _ = cycle_candidate(configured, run.cycle)
                with _target_lock(candidate):
                    if candidate.is_file():
                        if candidate.stat().st_size == 0:
                            raise InputUnavailable(
                                f"{name}: zero-length observation at {candidate}"
                            )
                        continue
                    found = find_local_cycle_input(candidate, run.cycle, name)
                    if found is not None:
                        continue
                    provider = providers.get(name) or _default_provider(name, run.cycle)
                    if provider is None:
                        raise InputUnavailable(
                            f"Observations for {request.cycle} unavailable: {candidate}. "
                            f"No acquisition provider configured for '{name}'."
                        )
                    if provider.get("type", "https") not in {"https", "https-tar"}:
                        raise ValueError(f"Unsupported observation provider type: {provider.get('type')}")
                    product = provider.get("product", "configured-provider")
                    print(
                        f"[OBS] {request.cycle}: acquiring {name} "
                        f"({product}) from GDEX/provider", flush=True
                    )
                    try:
                        _acquire_remote(candidate, run.cycle, name, provider)
                    except Exception as error:
                        raise InputUnavailable(
                            f"Could not acquire {name} for {request.cycle} at {candidate}: {error}"
                        ) from error
                    if not candidate.is_file() or candidate.stat().st_size == 0:
                        raise InputUnavailable(
                            f"{name}: provider did not publish a valid file: {candidate}"
                        )
                    acquired.append(candidate)
    return acquired
