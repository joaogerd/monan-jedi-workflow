from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from monan_jedi_workflow.config import load_experiment_config
from monan_jedi_workflow.render import render_pbs
from monan_jedi_workflow.site import render_site_environment_block
from monan_jedi_workflow.stage_config import (
    StageConfigurationError,
    render_declared_variables,
)


ROOT = Path(__file__).resolve().parents[1]


def test_stage_variables_expand_ecosystem_environment(monkeypatch) -> None:
    monkeypatch.setenv("MONAN_JEDI_INSTALL_ROOT", "/runtime/monan-jedi")
    monkeypatch.setenv("STACK_ROOT", "/runtime/spack-stack")

    context = render_declared_variables(
        {
            "variables": {
                "monan_jedi_install_root": "${MONAN_JEDI_INSTALL_ROOT}",
                "stack_root": "${STACK_ROOT}",
                "variational": "{monan_jedi_install_root}/bin/mpasjedi_variational.x",
            }
        },
        {"cycle_id": "20180415T000000Z"},
        label="jedi",
    )

    assert context["monan_jedi_install_root"] == "/runtime/monan-jedi"
    assert context["stack_root"] == "/runtime/spack-stack"
    assert context["variational"] == "/runtime/monan-jedi/bin/mpasjedi_variational.x"


def test_stage_variables_reject_missing_environment(monkeypatch) -> None:
    monkeypatch.delenv("MISSING_MONAN_RUNTIME", raising=False)

    with pytest.raises(StageConfigurationError, match="MISSING_MONAN_RUNTIME"):
        render_declared_variables(
            {"variables": {"root": "${MISSING_MONAN_RUNTIME}"}},
            {},
            label="jedi",
        )


def test_site_profile_uses_install_and_stack_roots(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MONAN_JEDI_INSTALL_ROOT", "/runtime/monan-jedi")
    monkeypatch.setenv("STACK_ROOT", "/runtime/spack-stack")
    site = tmp_path / "site.yaml"
    site.write_text(
        """
site:
  name: jaci
stack:
  load: true
  root: ${STACK_ROOT}
  env_name: jaci-mpas-jedi-gcc12-craympich
  env_module: cray-mpich/8.1.31/none/none/jedi-mpas-env/1.0.0
jedi:
  install_root: ${MONAN_JEDI_INSTALL_ROOT}
runtime:
  unload_anaconda: false
""",
        encoding="utf-8",
    )

    rendered = render_site_environment_block(site)

    assert 'export MONAN_JEDI_INSTALL_ROOT="/runtime/monan-jedi"' in rendered
    assert 'export STACK_ROOT="/runtime/spack-stack"' in rendered
    assert (
        'export STACK_MODULE_ROOT="/runtime/spack-stack/envs/'
        'jaci-mpas-jedi-gcc12-craympich/modules"'
    ) in rendered
    assert (
        'export STACK_SITE_SETUP="/runtime/spack-stack/configs/sites/tier2/jaci/setup.sh"'
    ) in rendered
    assert 'export PATH="${MONAN_JEDI_INSTALL_ROOT}/bin:${PATH}"' in rendered
    assert "MPAS_BUNDLE_BUILD" not in rendered


def test_site_profile_keeps_legacy_bundle_as_deprecated_fallback(tmp_path: Path) -> None:
    site = tmp_path / "legacy-site.yaml"
    site.write_text(
        """
site:
  name: test
stack:
  load: false
jedi:
  mpas_bundle_build: /legacy/build
""",
        encoding="utf-8",
    )

    with pytest.warns(DeprecationWarning, match="mpas_bundle_build"):
        rendered = render_site_environment_block(site)

    assert 'export MONAN_JEDI_INSTALL_ROOT="/legacy/build"' in rendered
    assert 'export MPAS_BUNDLE_BUILD="/legacy/build"' in rendered


@pytest.mark.parametrize(
    "relative",
    [
        "examples/simpleworkflow/cycled_da/jedi.yaml.example",
        "examples/simpleworkflow/cycled_da/jedi-baseline-bmatrix.yaml.example",
        "examples/simpleworkflow/cycled_da/mpas.yaml.example",
        "examples/simpleworkflow/cycled_da/mpas-cycling-jaci.yaml.example",
        "examples/simpleworkflow/cycled_da/obs2ioda.yaml.example",
        "examples/wps_gfs_operational/wps.yaml.example",
        "examples/mpas_init_x1_10242/mpas_init.yaml.example",
        "examples/obs2ioda/sondes/obs2ioda.yaml.example",
        "examples/obs2ioda/prepbufr-tutorial/obs2ioda.yaml.example",
        "examples/obs2ioda/prepbufr-operational/obs2ioda.yaml.example",
    ],
)
def test_maintained_examples_are_parseable_yaml(relative: str) -> None:
    document = yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
    assert isinstance(document, dict)


def test_cycling_examples_use_shared_runtime_contract() -> None:
    directory = ROOT / "examples/simpleworkflow/cycled_da"
    for name in (
        "jedi.yaml.example",
        "jedi-baseline-bmatrix.yaml.example",
        "mpas.yaml.example",
        "mpas-cycling-jaci.yaml.example",
        "obs2ioda.yaml.example",
    ):
        text = (directory / name).read_text(encoding="utf-8")
        assert "${MONAN_JEDI_INSTALL_ROOT}" in text
        assert "builds/monan-jedi-mpas" not in text

    for name in (
        "jedi.yaml.example",
        "jedi-baseline-bmatrix.yaml.example",
        "mpas.yaml.example",
        "mpas-cycling-jaci.yaml.example",
    ):
        text = (directory / name).read_text(encoding="utf-8")
        assert "${STACK_ROOT}" in text

    mpas = (directory / "mpas-cycling-jaci.yaml.example").read_text(encoding="utf-8")
    assert "mpas-bmatrix-global/scripts/load_jaci_env.sh" not in mpas


def test_legacy_renderer_no_longer_derives_source_or_build_roots() -> None:
    source = (ROOT / "monan_jedi_workflow/render.py").read_text(encoding="utf-8")

    assert "MONAN_JEDI_RUN_ID" not in source
    assert "MONAN_JEDI_SOURCE_DIR" not in source
    assert "MONAN_JEDI_BUILD_DIR" not in source
    assert "/builds/" not in source
    assert "MONAN_JEDI_INSTALL_ROOT must point to the public MONAN-JEDI installation" in source


def test_legacy_static_pbs_requires_and_bootstraps_shared_anchors() -> None:
    config = load_experiment_config(
        ROOT / "configs/experiments/3dfgat_mpastatic_x1.10242_2018041500"
    )
    rendered = render_pbs(config)

    assert "MONAN_JEDI_INSTALL_ROOT must point to the public MONAN-JEDI installation" in rendered
    assert "STACK_ROOT must point to the selected spack-stack checkout" in rendered
    assert 'pushd "${STACK_ROOT}" >/dev/null' in rendered
    assert 'module use "${STACK_ROOT}/envs/jaci-mpas-jedi-gcc12-craympich/modules"' in rendered
    assert "MONAN_JEDI_RUN_ID" not in rendered
    assert "/builds/" not in rendered
