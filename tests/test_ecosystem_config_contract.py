from __future__ import annotations

import json
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


def _write_runtime_contract(
    install_root: Path,
    *,
    public_anchors: list[str] | None = None,
) -> None:
    manifest = install_root / "share" / "monan-jedi" / "install-manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "ecosystem_contract_version": 2,
                "contract": "monan-jedi-runtime-v2",
                "public_anchors": public_anchors
                if public_anchors is not None
                else ["MONAN_JEDI_INSTALL_ROOT", "STACK_ROOT"],
                "stack": {
                    "env_name": "jaci-test",
                    "env_module": "test/jedi-mpas-env/2.0.0",
                    "site_setup": "configs/sites/tier2/jaci/setup.sh",
                    "module_root_template": "envs/{env_name}/modules",
                },
            }
        ),
        encoding="utf-8",
    )


def test_stage_variables_expand_ecosystem_environment(monkeypatch, tmp_path: Path) -> None:
    install = tmp_path / "monan-jedi"
    stack = tmp_path / "spack-stack"
    _write_runtime_contract(install)
    monkeypatch.setenv("MONAN_JEDI_INSTALL_ROOT", str(install))
    monkeypatch.setenv("STACK_ROOT", str(stack))

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

    assert context["monan_jedi_install_root"] == str(install)
    assert context["stack_root"] == str(stack)
    assert context["variational"] == str(install / "bin" / "mpasjedi_variational.x")
    assert context["stack_env_module"] == "test/jedi-mpas-env/2.0.0"


def test_stage_variables_require_installed_runtime_contract(
    monkeypatch, tmp_path: Path
) -> None:
    install = tmp_path / "missing-contract"
    monkeypatch.setenv("MONAN_JEDI_INSTALL_ROOT", str(install))
    monkeypatch.setenv("STACK_ROOT", str(tmp_path / "spack-stack"))

    with pytest.raises(StageConfigurationError, match="ecosystem contract v2"):
        render_declared_variables(
            {
                "variables": {
                    "monan_jedi_install_root": "${MONAN_JEDI_INSTALL_ROOT}",
                    "stack_root": "${STACK_ROOT}",
                }
            },
            {"cycle_id": "20180415T000000Z"},
            label="jedi",
        )


def test_stage_variables_reject_unexpected_runtime_public_anchors(
    monkeypatch, tmp_path: Path
) -> None:
    install = tmp_path / "monan-jedi"
    _write_runtime_contract(
        install,
        public_anchors=["MONAN_JEDI_INSTALL_ROOT"],
    )
    monkeypatch.setenv("MONAN_JEDI_INSTALL_ROOT", str(install))
    monkeypatch.setenv("STACK_ROOT", str(tmp_path / "spack-stack"))

    with pytest.raises(StageConfigurationError, match="public anchors"):
        render_declared_variables(
            {
                "variables": {
                    "monan_jedi_install_root": "${MONAN_JEDI_INSTALL_ROOT}",
                    "stack_root": "${STACK_ROOT}",
                }
            },
            {"cycle_id": "20180415T000000Z"},
            label="jedi",
        )


def test_stage_variables_reject_missing_environment(monkeypatch) -> None:
    monkeypatch.delenv("MISSING_MONAN_RUNTIME", raising=False)

    with pytest.raises(StageConfigurationError, match="MISSING_MONAN_RUNTIME"):
        render_declared_variables(
            {"variables": {"root": "${MISSING_MONAN_RUNTIME}"}},
            {},
            label="jedi",
        )


def test_site_profile_uses_install_and_stack_roots(monkeypatch, tmp_path: Path) -> None:
    install = tmp_path / "monan-jedi"
    stack_root = tmp_path / "spack-stack"
    _write_runtime_contract(install)
    monkeypatch.setenv("MONAN_JEDI_INSTALL_ROOT", str(install))
    monkeypatch.setenv("STACK_ROOT", str(stack_root))
    site = tmp_path / "site.yaml"
    site.write_text(
        """
site:
  name: jaci
stack:
  load: true
  root: ${STACK_ROOT}
jedi:
  install_root: ${MONAN_JEDI_INSTALL_ROOT}
runtime:
  unload_anaconda: false
""",
        encoding="utf-8",
    )

    rendered = render_site_environment_block(site)

    assert f'export MONAN_JEDI_INSTALL_ROOT="{install}"' in rendered
    assert f'export STACK_ROOT="{stack_root}"' in rendered
    assert "module purge" in rendered
    assert (
        f'export STACK_MODULE_ROOT="{stack_root}/envs/jaci-test/modules"'
    ) in rendered
    assert (
        f'export STACK_SITE_SETUP="{stack_root}/configs/sites/tier2/jaci/setup.sh"'
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
        "examples/case/campaign.yaml",
        "examples/case/profile.yaml",
        "examples/case/mpas.yaml",
        "examples/case/obs2ioda.yaml",
        "examples/case/jedi.yaml",
        "examples/case/initialization/mpas.yaml",
    ],
)
def test_maintained_examples_are_parseable_yaml(relative: str) -> None:
    document = yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))
    assert isinstance(document, dict)


def test_single_case_template_uses_shared_runtime_contract() -> None:
    for relative in ("examples/case/jedi.yaml", "examples/case/mpas.yaml"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "${MONAN_JEDI_INSTALL_ROOT}" in text
        assert "${STACK_ROOT}" in text
        assert "/p/projetos/" not in text

def test_legacy_renderer_no_longer_derives_source_or_build_roots() -> None:
    source = (ROOT / "monan_jedi_workflow/render.py").read_text(encoding="utf-8")

    assert "MONAN_JEDI_RUN_ID" not in source
    assert "MONAN_JEDI_SOURCE_DIR" not in source
    assert "MONAN_JEDI_BUILD_DIR" not in source
    assert "/builds/" not in source
    assert "pbs.environment_anchors.monan_jedi_install_root" in source
    assert "pbs.environment_anchors.stack_root" in source


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


def test_2025_reference_case_observers_match_declared_obs2ioda_outputs() -> None:
    obs = yaml.safe_load((ROOT / "examples/case/obs2ioda.yaml").read_text())["obs2ioda"]
    outputs = {
        Path(value).name
        for converter in obs["converters"]
        for value in converter["outputs"]
    }
    variational = (ROOT / "examples/case/templates/variational.yaml").read_text()
    assert "sondes_obs_{analysis_yyyymmddhh}.h5" in outputs
    assert "sfc_obs_{analysis_yyyymmddhh}.h5" in outputs
    assert "sondes_obs_{analysis_yyyymmddhh}_m.nc4" in variational
    assert "sfc_obs_{analysis_yyyymmddhh}_m.nc4" in variational
    assert "gnssro_obs_" not in variational
    assert "GnssroRefNCEP" not in variational
