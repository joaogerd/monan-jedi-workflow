"""Render MPAS-JEDI baseline YAML and PBS files.

This module converts the split experiment configuration into the concrete
application YAML consumed by ``mpasjedi_variational.x`` and into the PBS script
used to submit the baseline experiment on JACI-like systems.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import ExperimentConfig, require_key
from .runtime import get_rendered_dir, get_runtime_dir


def _quote(value: str) -> str:
    """Return a double-quoted string for YAML or shell-oriented output.

    Parameters
    ----------
    value : str
        Text value to quote.

    Returns
    -------
    str
        Value wrapped in double quotes.

    Raises
    ------
    None

    Notes
    -----
    The renderer builds YAML as text to preserve a layout close to the
    validated reference file. Explicit quoting avoids ambiguous parsing for
    path-like values.

    See Also
    --------
    render_yaml : Main consumer when rendering path fields.

    Examples
    --------
    >>> _quote("/tmp/file.nc")
    '"/tmp/file.nc"'
    """
    return f'"{value}"'


def _block_list(items: list[str], indent: int) -> list[str]:
    """Render a YAML block list with a fixed indentation.

    Parameters
    ----------
    items : list[str]
        Sequence of scalar values to render.
    indent : int
        Number of leading spaces before each ``-`` item marker.

    Returns
    -------
    list[str]
        Rendered YAML lines.

    Raises
    ------
    None

    Notes
    -----
    This helper is used for variable lists where block formatting improves
    readability and produces stable diffs against reference YAML files.

    See Also
    --------
    _inline_list : Render compact inline lists.
    render_yaml : Render model and analysis variable blocks.

    Examples
    --------
    >>> _block_list(["theta", "qv"], 2)
    ['  - theta', '  - qv']
    """
    pad = " " * indent
    return [f"{pad}- {item}" for item in items]


def _inline_list(items: list[str]) -> str:
    """Render a compact YAML inline list.

    Parameters
    ----------
    items : list[str]
        Sequence of scalar values to render.

    Returns
    -------
    str
        Inline YAML-style list.

    Raises
    ------
    None

    Notes
    -----
    Inline lists are used for short observation variable lists so the generated
    YAML remains close to the style commonly used in JEDI configuration files.

    See Also
    --------
    _block_list : Render multi-line YAML block lists.

    Examples
    --------
    >>> _inline_list(["airTemperature", "specificHumidity"])
    '[airTemperature, specificHumidity]'
    """
    return "[" + ", ".join(items) + "]"


def _render_simple_value(value: Any) -> str:
    """Render a scalar value using YAML-compatible text.

    Parameters
    ----------
    value : typing.Any
        Scalar value to render.

    Returns
    -------
    str
        Rendered scalar text. Booleans are converted to lowercase YAML
        literals.

    Raises
    ------
    None

    Notes
    -----
    Python renders booleans as ``True`` and ``False``, while YAML convention in
    the JEDI examples uses ``true`` and ``false``. This helper normalizes that
    specific case and leaves other values as strings.

    See Also
    --------
    _render_filters : Render observation filter mappings.

    Examples
    --------
    >>> _render_simple_value(True)
    'true'
    >>> _render_simple_value(10)
    '10'
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _render_filters(filters: list[dict[str, Any]], indent: int) -> list[str]:
    """Render observation filters into YAML lines.

    Parameters
    ----------
    filters : list[dict[str, typing.Any]]
        Observation filter configuration blocks from ``observations.yaml``.
    indent : int
        Number of spaces used to indent each filter entry.

    Returns
    -------
    list[str]
        Rendered YAML lines for the ``obs filters`` section.

    Raises
    ------
    KeyError
        If a filter entry does not contain the required ``filter`` key, or if a
        ``where`` entry does not contain the expected nested variable name.

    Notes
    -----
    The renderer currently supports the subset of filter syntax used by the
    validated baseline, including optional ``where`` clauses with ``minvalue``
    and ``maxvalue`` thresholds.

    See Also
    --------
    render_yaml : Insert rendered filters into each observer block.

    Examples
    --------
    >>> filters = [{"filter": "Bounds Check", "filter variables": "x"}]
    >>> _render_filters(filters, 2)
    ['  - filter: Bounds Check', '    filter variables: x']
    """
    lines: list[str] = []
    pad = " " * indent
    sub = " " * (indent + 2)
    sub2 = " " * (indent + 4)
    sub3 = " " * (indent + 6)

    for filt in filters:
        lines.append(f"{pad}- filter: {filt['filter']}")

        # Preserve the user-provided order for all filter keys except the
        # required filter name, which is already emitted as the list item header.
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
    """Render a POSIX shell export statement.

    Parameters
    ----------
    name : str
        Environment variable name.
    value : typing.Any
        Environment variable value.

    Returns
    -------
    str
        Shell line in the form ``export NAME="value"``.

    Raises
    ------
    None

    Notes
    -----
    Values are always quoted to protect whitespace and special characters in
    scheduler or MPI environment settings.

    See Also
    --------
    render_pbs : Use this helper for runtime environment variables.

    Examples
    --------
    >>> _shell_export("OMP_NUM_THREADS", 1)
    'export OMP_NUM_THREADS="1"'
    """
    return f'export {name}="{value}"'


def render_yaml(config: ExperimentConfig) -> str:
    """Render the validated 3D-FGAT MPASstatic YAML.

    Parameters
    ----------
    config : ExperimentConfig
        Loaded experiment configuration. The configuration should satisfy
        ``validate_experiment_config`` before rendering.

    Returns
    -------
    str
        Complete MPAS-JEDI YAML document as a string ending with a newline.

    Raises
    ------
    KeyError
        If required configuration fields are missing.
    TypeError
        If configuration sections contain incompatible structures.
    ValueError
        If path values cannot be converted to valid ``Path`` objects.

    Notes
    -----
    The YAML is rendered manually rather than through a generic YAML dumper.
    This preserves anchors, aliases, ordering and visual structure expected by
    MPAS-JEDI users comparing the generated file with the validated manual
    baseline.

    See Also
    --------
    write_rendered_yaml : Write this rendered text to disk.
    render_pbs : Render the matching PBS submission script.

    Examples
    --------
    >>> callable(render_yaml)
    True
    """
    experiment = require_key(config.experiment, "experiment", "experiment.yaml")
    cycle = require_key(config.experiment, "cycle", "experiment.yaml")
    method = require_key(config.experiment, "method", "experiment.yaml")
    variables = config.variables
    observations = require_key(config.observations, "observers", "observations.yaml")

    runtime_dir = get_runtime_dir(config).resolve()

    # MPAS geometry files are staged in the runtime directory with separate
    # outer and inner configurations for the nonlinear model and variational
    # inner-loop geometry.
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
        # Each observer follows the standard JEDI structure: obs space,
        # nonlinear operator, optional linearized operator, error model and
        # optional quality-control filters.
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

    # The output and variational blocks are currently fixed to the validated
    # baseline settings. Keeping them explicit makes the generated file easier
    # to audit when debugging MPAS-JEDI failures.
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
    """Render a PBS script for the validated JACI baseline experiment.

    Parameters
    ----------
    config : ExperimentConfig
        Loaded experiment configuration.

    Returns
    -------
    str
        Complete executable PBS shell script as a string.

    Raises
    ------
    KeyError
        If required PBS, experiment or JEDI fields are missing.
    ValueError
        If numeric PBS resource fields cannot be converted to integers.

    Notes
    -----
    The rendered script changes into the runtime directory, creates output/log
    directories, exports selected environment variables and launches the JEDI
    executable with the rendered YAML file. It does not submit itself.

    See Also
    --------
    write_rendered_pbs : Write this script to disk and make it executable.
    render_yaml : Render the YAML file consumed by the script.

    Examples
    --------
    >>> callable(render_pbs)
    True
    """
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

    # Map workflow-level keys to the actual environment variable names consumed
    # by OpenMP, OOPS/JEDI, Fortran I/O and HPE/Cray libfabric.
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
    """Render and write the MPAS-JEDI YAML file.

    Parameters
    ----------
    config : ExperimentConfig
        Loaded experiment configuration.

    Returns
    -------
    pathlib.Path
        Path to the rendered YAML file.

    Raises
    ------
    KeyError
        If required configuration fields are missing.
    OSError
        If the rendered directory cannot be created or the file cannot be
        written.

    Notes
    -----
    The output filename is derived from ``experiment.name``. This keeps
    generated artifacts self-describing when several experiments share the same
    rendered output directory.

    See Also
    --------
    render_yaml : Generate the YAML text.
    get_rendered_dir : Resolve the output directory.

    Examples
    --------
    >>> callable(write_rendered_yaml)
    True
    """
    rendered_dir = get_rendered_dir(config).resolve()
    experiment = require_key(config.experiment, "experiment", "experiment.yaml")
    rendered_dir.mkdir(parents=True, exist_ok=True)

    path = rendered_dir / f"{experiment['name']}.yaml"
    path.write_text(render_yaml(config))
    return path


def write_rendered_pbs(config: ExperimentConfig) -> Path:
    """Render and write an executable PBS script.

    Parameters
    ----------
    config : ExperimentConfig
        Loaded experiment configuration.

    Returns
    -------
    pathlib.Path
        Path to the rendered PBS script.

    Raises
    ------
    KeyError
        If required configuration fields are missing.
    OSError
        If the rendered directory cannot be created, the file cannot be
        written, or permissions cannot be changed.

    Notes
    -----
    The generated file is assigned mode ``0o755`` so it can be executed
    directly during manual testing. Submission is still left to the user or to a
    higher-level workflow step.

    See Also
    --------
    render_pbs : Generate the PBS script text.
    get_rendered_dir : Resolve the output directory.

    Examples
    --------
    >>> callable(write_rendered_pbs)
    True
    """
    rendered_dir = get_rendered_dir(config).resolve()
    experiment = require_key(config.experiment, "experiment", "experiment.yaml")
    rendered_dir.mkdir(parents=True, exist_ok=True)

    path = rendered_dir / f"{experiment['name']}.pbs"
    path.write_text(render_pbs(config))
    path.chmod(0o755)
    return path
