"""Compose selected components and explicit experiment overrides in memory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .components import deep_merge, resolve_experiment_components


def _mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{context} must be a YAML mapping")
    return value


def _without_selector(section: dict[str, Any], selector: str) -> dict[str, Any]:
    return {key: value for key, value in section.items() if key != selector}


def compose_cyclic_experiment(experiment_path: Path) -> dict[str, Any]:
    """Return an effective configuration without writing files.

    Component values are defaults. Values explicitly present in the minimal
    experiment are retained as overrides only for their own section. Component
    selectors themselves are removed from the effective sections because the
    resolved component is the authoritative detailed definition.
    """
    resolved = resolve_experiment_components(experiment_path)
    experiment = _mapping(resolved["experiment"], "experiment")
    components = _mapping(resolved["components"], "components")

    assimilation_choice = _mapping(experiment["assimilation"], "assimilation")
    forecast_choice = _mapping(experiment["forecast"], "forecast")
    background_choice = _mapping(experiment["background"], "background")
    bmatrix_choice = _mapping(experiment["bmatrix"], "bmatrix")
    geometry_choice = _mapping(experiment["geometry"], "geometry")
    observations_choice = _mapping(experiment["observations"], "observations")
    run_choice = _mapping(experiment["run"], "run")

    platform_defaults = _mapping(components["platform"].get("platform"), "platform")
    platform_default_run = _mapping(platform_defaults.get("defaults", {}), "platform.defaults")

    effective = {
        "experiment": experiment.get("experiment", {}),
        "cycle": _mapping(experiment["cycle"], "cycle"),
        "assimilation": deep_merge(
            _mapping(components["assimilation"].get("assimilation"), "component assimilation"),
            _without_selector(assimilation_choice, "method"),
        ),
        "forecast": deep_merge(
            _mapping(components["forecast"].get("forecast"), "component forecast"),
            _without_selector(forecast_choice, "profile"),
        ),
        "background": deep_merge(
            _mapping(components["background"].get("background"), "component background"),
            _without_selector(background_choice, "source"),
        ),
        "bmatrix": deep_merge(
            _mapping(components["bmatrix"].get("bmatrix"), "component bmatrix"),
            _without_selector(bmatrix_choice, "name"),
        ),
        "geometry": deep_merge(
            _mapping(components["geometry"].get("geometry"), "component geometry"),
            _without_selector(geometry_choice, "name"),
        ),
        "observations": deep_merge(
            _mapping(components["observations"].get("observations"), "component observations"),
            _without_selector(observations_choice, "set"),
        ),
        "run": deep_merge(platform_default_run, _without_selector(run_choice, "platform")),
        "platform": platform_defaults,
    }
    return effective
