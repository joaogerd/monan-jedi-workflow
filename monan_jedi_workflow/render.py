"""Render MPAS-JEDI baseline YAML and PBS files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import ExperimentConfig, require_key
from .runtime import get_runtime_dir, get_rendered_dir


def _quote(value: str) -> str:
    return f'"{value}"'


def _block_list(items: list[str], indent: int) -> list[str]:
    pad = " " * indent
    return [f"{pad}- {item}" for item in items]


def _inline_list(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


def _render_simple_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _render_filters(filters: list[dict[str, Any]], indent: int) -> list[str]:
    lines: list[str] = []
    pad = " " * indent
    sub = " " * (indent + 2)
    sub2 = " " * (indent + 4)
    sub3 = " " * (indent + 6)

    for filt in filters:
        lines.append(f"{pad}- filter: {filt['filter']}")
        for key, value in filt.items():
            if key == "filter":
                continue
            if key == "where":
                lines.append(f"{sub}where:")
                for entry in value:
                    lines.append(f"{sub}- variable:")
                    lines.append(f"{sub3}name: {entry['variable']['name']}")
                    if "minvalue" in entry:
                        lines.append(f"{sub2}minvalue: {entry['minvalue']}")
                    if "maxvalue" in entry:
                        lines.append(f"{sub2}maxvalue: {entry['maxvalue']}")
            else:
                lines.append(f"{sub}{key}: {_render_simple_value(value)}")

    return lines


def _shell_export(name: str, value: Any) -> str:
    return f'export {name}="{value}"'


def render_yaml(config: ExperimentConfig) -> str:
    """Render the validated 3D-FGAT MPASstatic YAML."""
    experiment = require_key(config.experiment, "experiment", "experiment.yaml")
    cycle = require_key(config.experiment, "cycle", "experiment.yaml")
    method = require_key(config.experiment, "method", "experiment.yaml")
    variables = config.variables
    observations = require_key(config.observations, "observers", "observations.yaml")

    runtime_dir = get_runtime_dir(config).resolve()

    outer_namelist = runtime_dir / "namelist.atmosphere.outer"
    outer_streams = runtime_dir / "streams.atmosphere.outer"
    inner_namelist = runtime_dir / "namelist.atmosphere.inner"
    inner_streams = runtime_dir / "streams.atmosphere.inner"

    background_name = f"mpasout.{cycle.get('mpas_background_file_date', '2018-04-14_21.00.00')}.nc"
    background_file = runtime_dir / "background" / background_name

    model_variables = require_key(variables, "model_variables", "variables.yaml")
    analysis_variables = require_key(variables, "analysis_variables", "variables.yaml")

    background_date = str(method.get("covariance_date", cycle.get("background_datetime")))

    lines: list[str] = [
        "cost function:",
        f"  cost type: {method['cost_type']}",
        "  time window:",
        f"    begin: '{cycle['window_begin']}'",
        f"    length: {cycle['window_length']}",
        "  geometry:",
        f"    nml_file: {_quote(str(outer_namelist))}",
        f"    streams_file: {_quote(str(outer_streams))}",
        "  model:",
        "    name: MPAS",
        f"    tstep: {experiment.get('model_tstep', 'PT45M')}",
        "    model variables: &modvars",
        *_block_list(model_variables, 4),
        "  analysis variables: &incvars",
        *_block_list(analysis_variables, 2),
        "  background:",
        "    state variables: *modvars",
        f"    filename: {_quote(str(background_file))}",
        f"    date: '{cycle['background_datetime']}'",
        "  background error:",
        f"    covariance model: {method['covariance_model']}",
        f"    date: '{background_date}'",
        "  observations:",
        "    observers:",
    ]

    for obs in observations:
        lines.extend(
            [
                "    - obs space:",
                f"        name: {obs['name']}",
                "        obsdatain:",
                "          engine:",
                "            type: H5File",
                f"            obsfile: {obs['obsdatain']['obsfile']}",
                "        obsdataout:",
                "          engine:",
                "            type: H5File",
                f"            obsfile: {obs['obsdataout']['obsfile']}",
                f"        simulated variables: {_inline_list(obs['simulated_variables'])}",
                "      obs operator:",
                f"        name: {obs['obs_operator']['name']}",
            ]
        )

        for key, value in obs.get("obs_operator", {}).items():
            if key == "name":
                continue
            if isinstance(value, dict):
                lines.append(f"        {key}:")
                for subkey, subvalue in value.items():
                    lines.append(f"          {subkey}: {_render_simple_value(subvalue)}")
            else:
                lines.append(f"        {key}: {_render_simple_value(value)}")

        if "linear_obs_operator" in obs:
            lines.extend(
                [
                    "      linear obs operator:",
                    f"        name: {obs['linear_obs_operator']['name']}",
                ]
            )
            for key, value in obs["linear_obs_operator"].items():
                if key == "name":
                    continue
                lines.append(f"        {key}: {_render_simple_value(value)}")

        lines.extend(
            [
                "      obs error:",
                "        covariance model: diagonal",
            ]
        )
        filters = obs.get("obs_filters", [])
        if filters:
            lines.append("      obs filters:")
            lines.extend(_render_filters(filters, 6))

    lines.extend(
        [
            "output:",
            '  filename: "Data/states/mpas.3dfgat.$Y-$M-$D_$h.$m.$s.nc"',
            "  stream name: analysis",
            "variational:",
            "  minimizer:",
            "    algorithm: DRPCG",
            "  iterations:",
            "  - geometry:",
            f"      nml_file: {_quote(str(inner_namelist))}",
            f"      streams_file: {_quote(str(inner_streams))}",
            "    ninner: '10'",
            "    gradient norm reduction: 1e-10",
            "    test: 'on'",
        ]
    )

    return "\n".join(lines) + "\n"


def render_pbs(config: ExperimentConfig) -> str:
    """Render a PBS script for the validated JACI baseline experiment."""
    pbs = require_key(config.pbs, "pbs", "pbs.yaml")
    experiment = require_key(config.experiment, "experiment", "experiment.yaml")
    jedi = require_key(config.experiment, "jedi", "experiment.yaml")

    runtime_dir = get_runtime_dir(config).resolve()
    rendered_dir = get_rendered_dir(config).resolve()
    yaml_file = rendered_dir / f"{experiment['name']}.yaml"

    job_name = pbs.get("job_name", experiment["name"])
    queue = pbs.get("queue", "pesqmini")
    walltime = pbs.get("walltime", "00:30:00")
    select = int(pbs.get("select", pbs.get("nodes", 1)))
    ncpus = int(pbs.get("ncpus", pbs.get("mpiprocs", 64)))
    mpiprocs = int(pbs.get("mpiprocs", 64))
    launcher = pbs.get("launcher", "mpiexec")
    executable = jedi["executable"]

    environment = pbs.get("environment", {})
    setup_script = environment.get("setup_script")
    site_env = environment.get("site_env")

    runtime_env = pbs.get("runtime", {})
    export_map = {
        "omp_num_threads": "OMP_NUM_THREADS",
        "oops_trace": "OOPS_TRACE",
        "oops_debug": "OOPS_DEBUG",
        "gfortran_convert_unit": "GFORTRAN_CONVERT_UNIT",
        "f_ufmtendian": "F_UFMTENDIAN",
        "fi_cxi_rx_match_mode": "FI_CXI_RX_MATCH_MODE",
    }
    export_lines = [
        _shell_export(env_name, runtime_env[key])
        for key, env_name in export_map.items()
        if key in runtime_env and runtime_env[key] is not None
    ]

    log_config = pbs.get("log", {})
    log_directory = log_config.get("directory", "logs")
    log_filename = log_config.get("filename", "run.${PBS_JOBID}.log")
    log_path = f"{log_directory}/{log_filename}"
    pbs_log_dir = runtime_dir / log_directory

    source_line = ""
    if setup_script and site_env:
        source_line = f"source {setup_script} {site_env}\n\n"

    exports_block = "\n".join(export_lines)
    if exports_block:
        exports_block += "\n\n"

    return f"""#!/usr/bin/env bash
#PBS -N {job_name}
#PBS -q {queue}
#PBS -l select={select}:ncpus={ncpus}:mpiprocs={mpiprocs}
#PBS -l walltime={walltime}
#PBS -j oe
#PBS -o {pbs_log_dir}

set -euo pipefail

{source_line}cd {runtime_dir}
mkdir -p Data/os Data/states {log_directory}

{exports_block}LOG="{log_path}"

{{
  echo "Job started at $(date -Is)"
  echo "Runtime directory: $(pwd)"
  echo "YAML file: {yaml_file}"
  echo "MPI ranks: {mpiprocs}"
  {launcher} -n {mpiprocs} {executable} {yaml_file}
  echo "Job finished at $(date -Is)"
}} > "${{LOG}}" 2>&1
"""


def write_rendered_yaml(config: ExperimentConfig) -> Path:
    rendered_dir = get_rendered_dir(config).resolve()
    experiment = require_key(config.experiment, "experiment", "experiment.yaml")
    rendered_dir.mkdir(parents=True, exist_ok=True)
    path = rendered_dir / f"{experiment['name']}.yaml"
    path.write_text(render_yaml(config))
    return path


def write_rendered_pbs(config: ExperimentConfig) -> Path:
    rendered_dir = get_rendered_dir(config).resolve()
    experiment = require_key(config.experiment, "experiment", "experiment.yaml")
    rendered_dir.mkdir(parents=True, exist_ok=True)
    path = rendered_dir / f"{experiment['name']}.pbs"
    path.write_text(render_pbs(config))
    path.chmod(0o755)
    return path
