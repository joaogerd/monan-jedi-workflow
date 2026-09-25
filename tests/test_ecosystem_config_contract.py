from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from monan_jedi_workflow.config import load_experiment_config
from monan_jedi_workflow.render import render_pbs
from monan_jedi_workflow.runtime import _physics_file_links, _resolve_source
from monan_jedi_workflow.site import render_site_environment_block
from monan_jedi_workflow.stage_config import (
    StageConfigurationError,
    render_declared_variables,
    render_text,
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
    assert "pbs.environment_anchors.monan_jedi_install_root" in source
    assert "pbs.environment_anchors.stack_root" in source


def test_legacy_static_pbs_requires_and_bootstraps_shared_anchors(monkeypatch) -> None:
    monkeypatch.setenv("MONAN_JEDI_INSTALL_ROOT", "/runtime/monan-jedi")
    monkeypatch.setenv("STACK_ROOT", "/runtime/spack-stack")
    config = load_experiment_config(
        ROOT / "configs/experiments/3dfgat_mpastatic_x1.10242_2018041500"
    )
    rendered = render_pbs(config)

    assert "export MONAN_JEDI_INSTALL_ROOT=/runtime/monan-jedi" in rendered
    assert "export STACK_ROOT=/runtime/spack-stack" in rendered
    assert 'pushd "${STACK_ROOT}" >/dev/null' in rendered
    assert 'module use "${STACK_ROOT}/envs/jaci-mpas-jedi-gcc12-craympich/modules"' in rendered
    assert rendered.index("set +u") < rendered.index("source configs/sites/tier2/jaci/setup.sh")
    assert rendered.index('if [[ "${monan_had_nounset}" == "1" ]]') > rendered.index(
        "source configs/sites/tier2/jaci/setup.sh"
    )
    assert "MONAN_JEDI_RUN_ID" not in rendered
    assert "/builds/" not in rendered



def test_legacy_static_pbs_rejects_missing_submission_anchor(monkeypatch) -> None:
    monkeypatch.delenv("MONAN_JEDI_INSTALL_ROOT", raising=False)
    monkeypatch.setenv("STACK_ROOT", "/runtime/spack-stack")
    config = load_experiment_config(
        ROOT / "configs/experiments/3dfgat_mpastatic_x1.10242_2018041500"
    )

    with pytest.raises(ValueError, match="MONAN_JEDI_INSTALL_ROOT"):
        render_pbs(config)


def test_maintained_jaci_bootstraps_protect_setup_from_nounset() -> None:
    paths = [
        ROOT / "configs/experiments/3dfgat_mpastatic_x1.10242_2018041500/pbs.yaml",
        ROOT / "examples/simpleworkflow/cycled_da/jedi.yaml.example",
        ROOT / "examples/simpleworkflow/cycled_da/jedi-baseline-bmatrix.yaml.example",
        ROOT / "examples/simpleworkflow/cycled_da/mpas.yaml.example",
        ROOT / "examples/simpleworkflow/cycled_da/mpas-cycling-jaci.yaml.example",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "set +u" in text
        assert "monan_had_nounset" in text
        assert text.index("set +u") < text.index("source configs/sites/tier2/jaci/setup.sh")



def test_cycle_jaci_bootstrap_shell_braces_survive_template_rendering() -> None:
    for relative, root_key in (
        ("examples/simpleworkflow/cycled_da/jedi.yaml.example", "jedi"),
        ("examples/simpleworkflow/cycled_da/jedi-baseline-bmatrix.yaml.example", "jedi"),
        ("examples/simpleworkflow/cycled_da/mpas.yaml.example", "mpas"),
        ("examples/simpleworkflow/cycled_da/mpas-cycling-jaci.yaml.example", "mpas"),
    ):
        document = yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
        bootstrap = document[root_key]["pbs"]["bootstrap"]
        rendered = [
            render_text(item, {"stack_root": "/runtime/spack-stack"}, label=relative)
            for item in bootstrap
        ]
        restore = next(item for item in rendered if "monan_had_nounset" in item and "if [[" in item)
        assert "${monan_had_nounset}" in restore



def test_static_baseline_runtime_uses_installed_support_only() -> None:
    path = ROOT / "configs/experiments/3dfgat_mpastatic_x1.10242_2018041500/runtime.yaml"
    text = path.read_text(encoding="utf-8")
    document = yaml.safe_load(text)
    runtime = document["runtime"]

    assert "/p/projetos/monan_das/joao.gerd" not in text
    assert "/projects/MONAN-JEDI" not in text
    assert "manual-tests/official-3dvar-baseline" not in text
    assert runtime["physics_files"]["root"] == (
        "${MONAN_JEDI_INSTALL_ROOT}/share/MPAS/core_atmosphere"
    )

    installed_sources = [
        item["source"]
        for item in runtime["required_links"]
        if str(item["source"]).startswith("${MONAN_JEDI_INSTALL_ROOT}")
    ]
    assert installed_sources
    assert all("/share/" in source for source in installed_sources)
    assert any("/share/monan-jedi/mpas-jedi/namelists/" in source for source in installed_sources)
    assert not any("/share/monan-jedi/ufo/" in source for source in installed_sources)
    assert any(item["source"] == "ufo/testinput_tier_1" for item in runtime["required_links"])


def test_runtime_paths_expand_install_anchor(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MONAN_JEDI_INSTALL_ROOT", "/runtime/monan-jedi")

    source = _resolve_source(
        "${MONAN_JEDI_INSTALL_ROOT}/share/monan-jedi/mpas-jedi/namelists/geovars.yaml",
        tmp_path,
    )
    assert source == Path(
        "/runtime/monan-jedi/share/monan-jedi/mpas-jedi/namelists/geovars.yaml"
    )

    links = _physics_file_links(
        {
            "physics_files": {
                "root": "${MONAN_JEDI_INSTALL_ROOT}/share/MPAS/core_atmosphere",
                "files": ["GENPARM.TBL"],
            }
        },
        tmp_path,
    )
    assert links == [
        (Path("/runtime/monan-jedi/share/MPAS/core_atmosphere/GENPARM.TBL"), "GENPARM.TBL")
    ]


def test_runtime_paths_reject_missing_install_anchor(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("MONAN_JEDI_INSTALL_ROOT", raising=False)

    with pytest.raises(ValueError, match="MONAN_JEDI_INSTALL_ROOT"):
        _resolve_source(
            "${MONAN_JEDI_INSTALL_ROOT}/share/monan-jedi/mpas-jedi/namelists/geovars.yaml",
            tmp_path,
        )
