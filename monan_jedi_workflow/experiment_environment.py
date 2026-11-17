"""Generate a transparent, per-experiment JACI scientific environment.

No remote discovery, fabricated paths, or modifications to the user's shell.
The generated environment.sh is sourced explicitly on the login and by PBS
workers. Existing exported values take precedence over discovered defaults.
"""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import re
import yaml


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


def discover_stacks(workspace: Path) -> list[Path]:
    """List validated local stack installations; never choose by sort order."""
    work = workspace / "work"
    if not work.is_dir():
        return []
    candidates = [
        candidate for candidate in work.glob("spack-stack*/spack-stack")
        if (candidate / "configs/sites/tier2/jaci/setup.sh").is_file()
    ]
    return sorted(set(candidate.resolve() for candidate in candidates))


def _discover_stack(workspace: Path) -> Path | None:
    candidates = discover_stacks(workspace)
    return candidates[0] if len(candidates) == 1 else None


def _defaults(root: Path) -> dict[str, Path]:
    workspace = _workspace(root)
    if not workspace:
        return {}
    shared = workspace.parent / "share" / "MONAN-JEDI-Data"
    defaults = {
        "MONAN_JEDI_INSTALL_ROOT": workspace / "build/monan-jedi",
        "MONAN_MESH_ROOT": shared / "meshes/quasi_uniform/x1.10242_240km",
        "MONAN_PHYSICS_ROOT": shared / "physics/mpas/files",
        "MONAN_BMATRIX_ROOT": shared / "covariance/x1.10242_240km/55levels",
        "MONAN_INPUT_ROOT": workspace / "external-inputs",
        "MONAN_GFS_ROOT": workspace / "data/gfs",
        "MONAN_LIBFABRIC_ROOT": Path("/opt/cray/libfabric/1.22.0/lib64"),
    }
    stack = _discover_stack(workspace)
    if stack:
        defaults["STACK_ROOT"] = stack
    return defaults



def initialize_site(root: Path, *, stack: Path | None = None,
                    install: Path | None = None,
                    environ: dict[str, str] | None = None) -> Path:
    """Configure first-time JACI workspace using real installations.

    Each directory must exist. Multiple stack candidates require explicit
    selection; no prior experiment or environment.sh is needed.
    """
    workspace = _workspace(Path(root))
    if workspace is None:
        raise ValueError(
            "Cannot initialize site outside /p/projetos/<group>/<user>. "
            "Pass an existing site with experiment create --site."
        )
    target = workspace / "site.yaml"
    if target.exists():
        raise FileExistsError(f"Site profile already exists: {target}; refusing overwrite")

    environment = dict(os.environ if environ is None else environ)
    defaults = _defaults(Path(root))
    if install is None:
        install = Path(environment.get("MONAN_JEDI_INSTALL_ROOT")
                       or defaults.get("MONAN_JEDI_INSTALL_ROOT", ""))
    install = Path(install).expanduser().resolve()
    if not install.is_dir():
        raise ValueError(
            f"MONAN-JEDI installation missing: {install}. "
            "Pass experiment site init --install /actual/installed/prefix."
        )

    if stack is None and environment.get("STACK_ROOT"):
        stack = Path(environment["STACK_ROOT"])
    if stack is None:
        candidates = discover_stacks(workspace)
        if len(candidates) != 1:
            detail = "\n".join(f"  - {p}" for p in candidates)
            raise ValueError(
                f"Cannot select a stack automatically: {len(candidates)} valid "
                f"candidates.\n{detail}\nUse experiment site init "
                "--stack /actual/stack/root (and --install if necessary)."
            )
        stack = candidates[0]
    stack = Path(stack).expanduser().resolve()
    if not stack.is_dir():
        raise ValueError(f"Selected STACK_ROOT does not exist: {stack}")

    from .site import runtime_contract_context
    contract = runtime_contract_context(install, stack)
    for key, relative in (
        ("stack_site_setup", contract["stack_site_setup"]),
        ("stack_module_root", contract["stack_module_root"]),
    ):
        candidate = Path(relative)
        candidate = candidate if candidate.is_absolute() else stack / candidate
        if not (candidate.is_file() if key == "stack_site_setup" else candidate.is_dir()):
            raise ValueError(f"Installed runtime contract {key} missing: {candidate}")

    chosen = {
        "MONAN_JEDI_INSTALL_ROOT": str(install),
        "STACK_ROOT": str(stack),
    }
    missing = []
    for name in REQUIRED:
        if name in chosen:
            continue
        value = environment.get(name) or defaults.get(name)
        if value and Path(value).is_dir():
            chosen[name] = str(Path(value).resolve())
        else:
            missing.append(f"{name}: {value or 'not configured'}")
    if missing:
        raise ValueError(
            "Scientific directories could not be discovered:\n  "
            + "\n  ".join(missing)
            + "\nSet these roots to valid directories or provide a "
              "complete JACI site profile with experiment create --site."
        )

    document = {
        "site": {"name": "jaci"},
        "stack": {"load": True, "root": chosen["STACK_ROOT"]},
        "jedi": {"install_root": chosen["MONAN_JEDI_INSTALL_ROOT"]},
        "environment": {name: chosen[name] for name in REQUIRED
                        if name not in ("STACK_ROOT", "MONAN_JEDI_INSTALL_ROOT")},
        "runtime": {"unload_anaconda": True, "validate_python": False},
    }
    with target.open("x", encoding="utf-8") as output:
        yaml.safe_dump(document, output, sort_keys=False)
    return target


def load_project_site(root: Path, *, site_config: Path | None = None,
                      environ: dict[str, str] | None = None) -> tuple[Path | None, dict]:
    """Find the site profile explicitly or in the workspace, not by guessing stacks.

    A shared <workspace>/site.yaml is the stable, one-time JACI configuration
    for new experiments. CLI --site can select a different existing profile.
    The installed MONAN-JEDI v2 manifest still owns module identity.
    """
    env = dict(os.environ if environ is None else environ)
    workspace = _workspace(Path(root))
    if site_config is None:
        candidate = workspace / "site.yaml" if workspace else None
        if candidate is None or not candidate.is_file():
            if workspace is not None:
                # First-run bootstrap: discover valid JACI installations and
                # create the site profile once, before writing any case files.
                initialized = initialize_site(root, environ=env)
                return load_project_site(root, site_config=initialized, environ=env)
            return None, {}
        site_config = candidate
    path = Path(site_config).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"Site profile does not exist: {path}. "
            "Create a shared site.yaml or pass --site with an existing profile."
        )
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("site"), dict):
        raise ValueError(f"{path}: expected site: mapping")
    if not isinstance(payload.get("stack"), dict) or not isinstance(payload.get("jedi"), dict):
        raise ValueError(f"{path}: expected stack: and jedi: mappings")
    resolved = dict(payload)
    for section, key in (("stack", "root"), ("jedi", "install_root")):
        value = payload[section].get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{path}: {section}.{key} must be a nonempty path")
        expanded = os.path.expandvars(value)
        if re.search(r"\$(?:\{|[A-Za-z_])", expanded):
            raise ValueError(
                f"{path}: unresolved environment variable in {section}.{key}. "
                "A shared site profile should use a real, stable path."
            )
        target = Path(expanded).expanduser()
        if not target.is_absolute() or not target.is_dir():
            raise ValueError(f"{path}: {section}.{key} is not an existing absolute directory: {target}")
        resolved[section] = {**payload[section], key: str(target.resolve())}

    extra = payload.get("environment", {})
    if not isinstance(extra, dict):
        raise ValueError(f"{path}: environment must be a mapping")
    unknown = set(extra) - (set(REQUIRED) - {'STACK_ROOT', 'MONAN_JEDI_INSTALL_ROOT'})
    if unknown:
        raise ValueError(f"{path}: unsupported environment keys: {', '.join(sorted(unknown))}")
    extras = {}
    for key, value in extra.items():
        if not isinstance(value, str) or not value:
            raise ValueError(f"{path}: environment.{key} must be a nonempty path")
        expanded = os.path.expandvars(value)
        if re.search(r"\$(?:\{|[A-Za-z_])", expanded):
            raise ValueError(f"{path}: environment.{key} contains an undefined variable")
        target = Path(expanded).expanduser()
        if not target.is_absolute() or not target.is_dir():
            raise ValueError(f"{path}: environment.{key} directory does not exist: {target}")
        extras[key] = str(target.resolve())
    resolved["environment"] = extras
    return path, resolved



def save_project_site(root: Path, *, environ: dict[str, str] | None = None) -> Path:
    """One-time persistent site profile from a proven, explicitly loaded runtime.

    Never overwrite an existing site profile or silently pick among multiple
    stacks. The user must first source a working experiment environment.
    """
    env = dict(os.environ if environ is None else environ)
    workspace = _workspace(Path(root))
    if workspace is None:
        raise ValueError(
            "Workspace is not under /p/projetos/<group>/<user>; "
            "select an existing JACI workspace before saving its site configuration."
        )
    values = {}
    for name in REQUIRED:
        value = env.get(name, "").strip()
        if not value or not Path(value).is_dir():
            raise ValueError(
                f"{name} must refer to an existing directory before saving site.yaml. "
                "Source the environment.sh of a validated experiment first."
            )
        values[name] = str(Path(value).resolve())
    path = workspace / "site.yaml"
    if path.exists():
        raise FileExistsError(
            f"Refusing to overwrite the existing site profile: {path}"
        )
    # The installed producer is authoritative for module name/site setup.
    from .site import runtime_contract_context
    runtime_contract_context(values["MONAN_JEDI_INSTALL_ROOT"], values["STACK_ROOT"])
    document = {
        "site": {"name": "jaci"},
        "stack": {"load": True, "root": values["STACK_ROOT"]},
        "jedi": {"install_root": values["MONAN_JEDI_INSTALL_ROOT"]},
        "environment": {
            key: values[key] for key in REQUIRED
            if key not in ("STACK_ROOT", "MONAN_JEDI_INSTALL_ROOT")
        },
        "runtime": {"unload_anaconda": True, "validate_python": False},
    }
    with path.open("x", encoding="utf-8") as handle:
        yaml.safe_dump(document, handle, sort_keys=False)
    return path


def render_environment(root: Path, *, environ: dict[str, str] | None = None,
                       site_profile: dict | None = None) -> str:
    """Only select defaults actually present, never claim an unknown path exists."""
    env = dict(os.environ if environ is None else environ)
    defaults = _defaults(root)
    profile_values = {}
    if site_profile:
        profile_values = {
            "STACK_ROOT": Path(site_profile["stack"]["root"]),
            "MONAN_JEDI_INSTALL_ROOT": Path(site_profile["jedi"]["install_root"]),
            **{k: Path(v) for k, v in site_profile.get("environment", {}).items()},
        }
        defaults.update(profile_values)
    lines = [
        "#!/usr/bin/env bash",
        "# Generated scientific input/runtime configuration for this experiment.",
        "# Existing exported values override discovered candidates.",
        "# Run: source ./environment.sh",
        "# To change one entry: export MONAN_...=/p/... before sourcing.",
        "# This script never downloads, creates or substitutes scientific data.",
        "# Explicit site-profile values take precedence over inherited shell values.",
    ]
    for key in REQUIRED:
        candidate = defaults.get(key)
        selected = env.get(key, "").strip()
        origin = "existing export" if selected else "existing site path"
        if key in profile_values:
            selected = str(profile_values[key])
            lines.append(f'# {key}: declared by site.yaml')
            lines.append(f'export {key}=' + shlex.quote(selected))
            continue
        if not selected and candidate and candidate.is_dir():
            selected = str(candidate)
        if selected:
            # Use shell quoting; do not interpolate arbitrary paths into shell code.
            lines.append(f'# {key}: {origin}')
            lines.append(f'if [[ -z "${{{key}:-}}" ]]; then export {key}='
                         + shlex.quote(selected) + '; fi')
        else:
            lines.append(f'# {key}: not discovered; export an existing path first')
    # Optional existing JACI module loader. Do not require external repositories
    # when the user operates on another HPC site.
    workspace = _workspace(root)
    loader = (workspace / "projects/mpas-bmatrix-global/scripts/load_jaci_env.sh"
              if workspace is not None else None)
    loader_value = env.get("MONAN_JACI_LOADER", "").strip()
    if not loader_value and loader is not None and loader.is_file():
        loader_value = str(loader)
    if loader_value:
        lines.append('if [[ -z "${MONAN_JACI_LOADER:-}" ]]; then export MONAN_JACI_LOADER='
                     + shlex.quote(loader_value) + '; fi')
    else:
        lines.append("# MONAN_JACI_LOADER optional: set to an existing site module loader in /p")
    lines += [
        "_monan_env_missing=0",
        "for _monan_env_name in " + " ".join(REQUIRED) + "; do",
        '  if [[ -z "${!_monan_env_name:-}" ]]; then',
        '    printf "[CONFIGURACAO] %s nao definido. Configure um caminho real.\n" "$_monan_env_name" >&2',
        "    _monan_env_missing=1",
        '  elif [[ ! -d "${!_monan_env_name}" ]]; then',
        '    printf "[CONFIGURACAO] %s aponta para diretorio inexistente: %s\n" "$_monan_env_name" "${!_monan_env_name}" >&2',
        "    _monan_env_missing=1",
        "  fi",
        "done",
        'if [[ "$_monan_env_missing" -ne 0 ]]; then',
        '  echo "[CONFIGURACAO] Ambiente incompleto: corrija as variaveis acima antes de campaign check." >&2',
        '  return 2 2>/dev/null || exit 2',
        'fi',
        "unset _monan_env_missing _monan_env_name",
        'echo "[OK] Variaveis cientificas carregadas e diretorios presentes."',
    ]
    return "\n".join(lines) + "\n"
