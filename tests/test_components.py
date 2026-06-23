"""Tests for declarative component resolution without rendering side effects."""

from pathlib import Path

import pytest

from monan_jedi_workflow.components import (
    ComponentRepository,
    deep_merge,
    resolve_experiment_components,
)


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def create_component_tree(tmp_path: Path) -> Path:
    root = tmp_path / "configs"
    write(
        root / "experiments/example.yaml",
        """
assimilation: {method: 3dvar_fgat}
forecast: {profile: mpas_fgat_3h}
background: {source: previous_forecast}
bmatrix: {name: mpasstatic_x1.10242}
geometry: {name: x1.10242}
observations: {set: conv_basic}
run: {site: jaci}
""",
    )
    values = {
        "assimilation/3dvar_fgat.yaml": "method: {kind: 3D-FGAT}\n",
        "forecast/mpas_fgat_3h.yaml": "forecast: {output_interval_hours: 3}\n",
        "background/previous_forecast.yaml": "background: {kind: forecast}\n",
        "bmatrix/mpasstatic_x1.10242.yaml": "bmatrix: {type: MPASstatic}\n",
        "geometry/x1.10242.yaml": "geometry: {mesh: x1.10242}\n",
        "observations/conv_basic.yaml": "observations: {members: [radiosonde]}\n",
        "sites/jaci.yaml": "site: {scheduler: PBS}\n",
    }
    for relative, content in values.items():
        write(root / relative, content)
    return root


def test_resolve_experiment_components_loads_all_named_parts(tmp_path: Path) -> None:
    root = create_component_tree(tmp_path)

    resolved = resolve_experiment_components(root / "experiments/example.yaml")

    assert resolved["components"]["assimilation"]["method"]["kind"] == "3D-FGAT"
    assert resolved["components"]["forecast"]["forecast"]["output_interval_hours"] == 3
    assert resolved["components"]["site"]["site"]["scheduler"] == "PBS"
    assert resolved["experiment"]["observations"]["set"] == "conv_basic"


def test_legacy_platform_selector_is_site_alias(tmp_path: Path) -> None:
    root = create_component_tree(tmp_path)
    write(root / "experiments/example.yaml", """
assimilation: {method: 3dvar_fgat}
forecast: {profile: mpas_fgat_3h}
background: {source: previous_forecast}
bmatrix: {name: mpasstatic_x1.10242}
geometry: {name: x1.10242}
observations: {set: conv_basic}
run: {platform: jaci}
""")

    resolved = resolve_experiment_components(root / "experiments/example.yaml")

    assert resolved["components"]["site"]["site"]["scheduler"] == "PBS"


def test_component_resolver_reports_missing_component(tmp_path: Path) -> None:
    root = create_component_tree(tmp_path)
    (root / "forecast/mpas_fgat_3h.yaml").unlink()

    with pytest.raises(FileNotFoundError, match="mpas_fgat_3h"):
        resolve_experiment_components(root / "experiments/example.yaml")


def test_component_repository_rejects_path_traversal(tmp_path: Path) -> None:
    root = create_component_tree(tmp_path)
    repository = ComponentRepository(root)

    with pytest.raises(ValueError, match="Invalid component name"):
        repository.load("forecast", "../secret")


def test_deep_merge_preserves_defaults_and_replaces_lists() -> None:
    result = deep_merge(
        {"a": {"b": 1, "c": [1, 2]}, "d": 1},
        {"a": {"c": [3], "e": 2}, "d": 4},
    )

    assert result == {"a": {"b": 1, "c": [3], "e": 2}, "d": 4}
