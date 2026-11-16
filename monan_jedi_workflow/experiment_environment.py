"""Generate a transparent, per-experiment JACI scientific environment.

No remote discovery, fabricated paths, or modifications to the user's shell.
The generated environment.sh is sourced explicitly on the login and by PBS
workers. Existing exported values take precedence over discovered defaults.
"""
from __future__ import annotations

import os
from pathlib import Path
import shlex


REQUIRED = (
    "MONAN_JEDI_INSTALL_ROOT",
    "STACK_ROOT",
    "MONAN_MESH_ROOT",
    "MONAN_PHYSICS_ROOT",
    "MONAN_BMATRIX_ROOT",
    "MONAN_INPUT_ROOT",
    "MONAN_GFS_ROOT",
    "MONAN_LIBFABRIC_ROOT",
)


def _workspace(root: Path) -> Path | None:
    parts = root.resolve().parts
    if len(parts) >= 5 and parts[:3] == ("/", "p", "projetos"):
        return Path(*parts[:5])
    return None


def _defaults(root: Path) -> dict[str, Path]:
    workspace = _workspace(root)
    if not workspace:
        return {}
    shared = workspace.parent / "share" / "MONAN-JEDI-Data"
    return {
        "MONAN_JEDI_INSTALL_ROOT": workspace / "build/monan-jedi",
        "STACK_ROOT": Path("/p/projetos/monan_das/joao.gerd/work/"
                           "spack-stack-inpe-overlay-20260515T181917Z/spack-stack"),
        "MONAN_MESH_ROOT": shared / "meshes/quasi_uniform/x1.10242_240km",
        "MONAN_PHYSICS_ROOT": shared / "physics/mpas/files",
        "MONAN_BMATRIX_ROOT": shared / "covariance/x1.10242_240km/55levels",
        "MONAN_INPUT_ROOT": workspace / "external-inputs",
        "MONAN_GFS_ROOT": workspace / "data/gfs",
        "MONAN_LIBFABRIC_ROOT": Path("/opt/cray/libfabric/1.22.0/lib64"),
    }


def render_environment(root: Path, *, environ: dict[str, str] | None = None) -> str:
    """Only select defaults actually present, never claim an unknown path exists."""
    env = dict(os.environ if environ is None else environ)
    defaults = _defaults(root)
    lines = [
        "#!/usr/bin/env bash",
        "# Generated scientific input/runtime configuration for this experiment.",
        "# Existing exported values override discovered candidates.",
        "# Run: source ./environment.sh",
        "# To change one entry: export MONAN_...=/p/... before sourcing.",
        "# This script never downloads, creates or substitutes scientific data.",
    ]
    for key in REQUIRED:
        candidate = defaults.get(key)
        selected = env.get(key, "").strip()
        if not selected and candidate and candidate.exists():
            selected = str(candidate)
        lines.append(f'export {key}="${{{key}:-{selected}}}"'
                     if selected and '"' not in selected and '$' not in selected and '`' not in selected
                     else f'export {key}="${{{key}:-}}"')
        # Unsafe shell metacharacters are never injected into the generated script.
        if not selected:
            lines.append(f'# {key}: not discovered; set explicitly with export before sourcing')
    lines += [
        "_monan_env_missing=0",
        "for _monan_env_name in " + " ".join(REQUIRED) + "; do",
        '  if [[ -z "${!_monan_env_name:-}" ]]; then',
        '    printf "[CONFIGURACAO] %s nao definido. Exporte um caminho real em /p.\\n" "$_monan_env_name" >&2',
        "    _monan_env_missing=1",
        "  fi",
        "done",
        'if [[ "$_monan_env_missing" -ne 0 ]]; then',
        '  echo "[CONFIGURACAO] Ambiente incompleto: consulte environment.sh e docs/first-experiment.md." >&2',
        '  return 2 2>/dev/null || exit 2',
        'fi',
        "unset _monan_env_missing _monan_env_name",
        'echo "[OK] Variaveis cientificas carregadas para o experimento."',
    ]
    return "\n".join(lines) + "\n"
