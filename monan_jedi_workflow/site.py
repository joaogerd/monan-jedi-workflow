"""Site-specific environment rendering utilities.

This module keeps site configuration in YAML and renders the shell block that
must run inside the PBS job. Python does not load environment modules into the
current process; it only generates an auditable shell snippet for the job script.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .config import require_key


def _quote_shell(value: Any) -> str:
    """Return a safely double-quoted shell value for simple site settings."""
    text = str(value)
    return '"' + text.replace('"', '\\"') + '"'


def _export(name: str, value: Any) -> str:
    return f"export {name}={_quote_shell(value)}"


def load_site_config(path: str | Path) -> dict[str, Any]:
    """Load a site YAML configuration file."""
    site_path = Path(path)
    if not site_path.is_file():
        raise FileNotFoundError(f"Site configuration file not found: {site_path}")
    with site_path.open() as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise TypeError(f"Site configuration must be a mapping: {site_path}")
    return data


def render_site_environment_block(path: str | Path) -> str:
    """Render a PBS shell block from a site YAML configuration."""
    config = load_site_config(path)

    site = require_key(config, "site", "site.yaml")
    stack = config.get("stack", {})
    jedi = require_key(config, "jedi", "site.yaml")
    mpi = config.get("mpi", {})
    runtime = config.get("runtime", {})

    lines: list[str] = [
        "# ---- site environment ----",
        _export("MONAN_SITE", require_key(site, "name", "site.yaml site")),
    ]

    optional_site_exports = {
        "workspace": "MONAN_JACI_WORKSPACE",
        "workflow_root": "MONAN_WORKFLOW_ROOT",
        "work_root": "MONAN_WORK_ROOT",
        "scratch": "MONAN_SCRATCH",
        "data_root": "MONAN_DATA_ROOT",
        "external_data_root": "MONAN_EXTERNAL_DATA_ROOT",
        "experiment_root": "MONAN_EXPERIMENT_ROOT",
    }
    for key, env_name in optional_site_exports.items():
        if key in site and site[key] is not None:
            lines.append(_export(env_name, site[key]))

    mpas_bundle_build = require_key(jedi, "mpas_bundle_build", "site.yaml jedi")
    variational_exe = require_key(jedi, "variational_exe", "site.yaml jedi")
    lines.extend(
        [
            _export("MPAS_BUNDLE_BUILD", mpas_bundle_build),
            _export("MPASJEDI_VARIATIONAL_EXE", variational_exe),
        ]
    )

    if "launcher" in mpi:
        lines.append(_export("MPI_LAUNCHER", mpi["launcher"]))
    if "tasks_flag" in mpi:
        lines.append(_export("MPI_TASKS_FLAG", mpi["tasks_flag"]))

    if stack.get("load", False):
        stack_root = require_key(stack, "root", "site.yaml stack")
        stack_module_root = require_key(stack, "module_root", "site.yaml stack")
        stack_env_module = require_key(stack, "env_module", "site.yaml stack")
        stack_site_setup = require_key(stack, "site_setup", "site.yaml stack")
        stack_env_name = stack.get("env_name")

        lines.append(_export("MONAN_LOAD_STACK", "true"))
        lines.append(_export("STACK_ROOT", stack_root))
        if stack_env_name:
            lines.append(_export("STACK_ENV_NAME", stack_env_name))
        lines.append(_export("STACK_MODULE_ROOT", stack_module_root))
        lines.append(_export("STACK_ENV_MODULE", stack_env_module))
        lines.append(_export("STACK_SITE_SETUP", stack_site_setup))

        lines.extend(
            [
                "",
                "case \"$-\" in",
                "  *u*) monan_had_nounset=1 ;;",
                "  *) monan_had_nounset=0 ;;",
                "esac",
                "set +u",
                "[[ -d \"${STACK_ROOT}\" ]] || { echo \"[ERROR] STACK_ROOT not found: ${STACK_ROOT}\" >&2; exit 1; }",
                "[[ -d \"${STACK_MODULE_ROOT}\" ]] || { echo \"[ERROR] STACK_MODULE_ROOT not found: ${STACK_MODULE_ROOT}\" >&2; exit 1; }",
                "[[ -f \"${STACK_SITE_SETUP}\" ]] || { echo \"[ERROR] STACK_SITE_SETUP not found: ${STACK_SITE_SETUP}\" >&2; exit 1; }",
                "monan_previous_dir=\"$(pwd)\"",
                "cd \"${STACK_ROOT}\"",
                "source \"${STACK_SITE_SETUP}\"",
                "module use \"${STACK_MODULE_ROOT}\"",
                "module load \"${STACK_ENV_MODULE}\"",
            ]
        )
        if runtime.get("unload_anaconda", True):
            lines.extend(
                [
                    "module unload anaconda/24.1.2 >/dev/null 2>&1 || true",
                    "module unload anaconda >/dev/null 2>&1 || true",
                    "hash -r 2>/dev/null || true",
                ]
            )
        lines.extend(
            [
                "cd \"${monan_previous_dir}\"",
                "if [[ \"${monan_had_nounset}\" == \"1\" ]]; then set -u; else set +u; fi",
                "unset monan_had_nounset monan_previous_dir",
            ]
        )

    lines.extend(
        [
            "export PATH=\"${MPAS_BUNDLE_BUILD}/bin:${PATH}\"",
            "export LD_LIBRARY_PATH=\"${MPAS_BUNDLE_BUILD}/lib:${LD_LIBRARY_PATH:-}\"",
        ]
    )

    if runtime.get("validate_python", False):
        expected_abi = runtime.get("expected_python_abi")
        if expected_abi:
            lines.extend(
                [
                    "python3 - <<'PY'",
                    "import sys",
                    f"expected = {expected_abi!r}",
                    "actual = f'{sys.version_info.major}.{sys.version_info.minor}'",
                    "if actual != expected:",
                    "    raise SystemExit(f'wrong Python ABI: expected {expected}, got {actual}')",
                    "PY",
                ]
            )

    lines.append("# ---- end site environment ----")
    return "\n".join(lines) + "\n"
