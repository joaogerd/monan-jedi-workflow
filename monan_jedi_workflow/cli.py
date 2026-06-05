"""Command-line interface for the minimal MONAN-JEDI workflow.

This module provides the public command-line entry point used to validate an
experiment configuration, stage runtime inputs, and render MPAS-JEDI YAML/PBS
files for the baseline MONAN-JEDI workflow.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_experiment_config, validate_experiment_config
from .render import write_rendered_pbs, write_rendered_yaml
from .runtime import prepare_runtime


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for the workflow executable.

    Parameters
    ----------
    None

    Returns
    -------
    argparse.ArgumentParser
        Configured parser containing all supported workflow subcommands.

    Raises
    ------
    None

    Notes
    -----
    The parser intentionally keeps a small command surface. Each subcommand
    receives a single ``config_dir`` argument, which points to a directory
    containing the split YAML configuration files required by the workflow.

    See Also
    --------
    main : Parse command-line arguments and dispatch to the selected command.
    run_validate : Validate an experiment configuration directory.
    run_prepare : Validate and prepare the runtime directory.
    run_render_yaml : Render the MPAS-JEDI application YAML file.
    run_render_pbs : Render the PBS submission script.

    Examples
    --------
    >>> parser = build_parser()
    >>> args = parser.parse_args(["validate-config", "configs/example"])
    >>> args.command
    'validate-config'
    >>> args.config_dir
    PosixPath('configs/example')
    """
    parser = argparse.ArgumentParser(
        prog="monan-jedi-workflow",
        description="Minimal Python-first workflow for MONAN MPAS-JEDI experiments.",
    )

    # All commands currently share the same positional argument. Keeping this
    # loop avoids duplicating parser configuration while preserving independent
    # subcommands for validation, staging, and rendering.
    sub = parser.add_subparsers(dest="command", required=True)

    for cmd in ["validate-config", "prepare-runtime", "render-yaml", "render-pbs"]:
        p = sub.add_parser(cmd)
        p.add_argument("config_dir", type=Path)

    return parser


def run_validate(config_dir: Path) -> int:
    """Validate the experiment configuration files.

    Parameters
    ----------
    config_dir : pathlib.Path
        Directory containing the required split YAML files, such as
        ``experiment.yaml``, ``runtime.yaml``, ``variables.yaml``,
        ``observations.yaml`` and ``pbs.yaml``.

    Returns
    -------
    int
        Process-style return code. A value of ``0`` indicates successful
        validation.

    Raises
    ------
    FileNotFoundError
        If one of the required YAML files does not exist.
    KeyError
        If a required configuration key is missing.
    TypeError
        If a YAML file does not contain the expected mapping structure.
    ValueError
        If the configuration does not match the supported baseline contract.

    Notes
    -----
    Validation messages are printed to standard output using an ``[OK]``
    prefix. Exceptions are intentionally allowed to propagate so that the
    command-line process fails loudly during automated tests or HPC setup.

    See Also
    --------
    load_experiment_config : Load the split YAML configuration files.
    validate_experiment_config : Validate the baseline experiment contract.

    Examples
    --------
    >>> from pathlib import Path
    >>> # run_validate(Path("configs/experiments/3dfgat_mpastatic_x1.10242_2018041500"))
    >>> isinstance(Path("configs"), Path)
    True
    """
    cfg = load_experiment_config(config_dir)

    # Each validation message is emitted independently so users can see which
    # parts of the baseline contract were checked successfully.
    for msg in validate_experiment_config(cfg):
        print(f"[OK] {msg}")

    return 0


def run_prepare(config_dir: Path) -> int:
    """Validate the configuration and prepare the runtime directory.

    Parameters
    ----------
    config_dir : pathlib.Path
        Directory containing the split YAML configuration files for one
        MONAN-JEDI experiment.

    Returns
    -------
    int
        Process-style return code. A value of ``0`` indicates that validation
        and runtime staging completed successfully.

    Raises
    ------
    FileNotFoundError
        If a required configuration file or staged runtime source is missing.
    FileExistsError
        If a runtime target exists and is not a symbolic link.
    KeyError
        If a required configuration key is missing.
    TypeError
        If a runtime link entry has an invalid structure.
    ValueError
        If the configuration violates the baseline experiment contract.

    Notes
    -----
    Runtime preparation is idempotent for symbolic links that already point to
    the requested source. Existing non-link files are never overwritten because
    they may contain manually produced experiment outputs.

    See Also
    --------
    prepare_runtime : Create directories and symbolic links for execution.
    validate_experiment_config : Validate the experiment before staging files.

    Examples
    --------
    >>> from pathlib import Path
    >>> # run_prepare(Path("configs/experiments/3dfgat_mpastatic_x1.10242_2018041500"))
    >>> Path("runtime").name
    'runtime'
    """
    cfg = load_experiment_config(config_dir)

    # Always validate before touching the filesystem. This prevents partially
    # staged runtime directories from being created from inconsistent inputs.
    for msg in validate_experiment_config(cfg):
        print(f"[OK] {msg}")

    for msg in prepare_runtime(cfg):
        print(msg)

    return 0


def run_render_yaml(config_dir: Path) -> int:
    """Render the MPAS-JEDI YAML configuration file.

    Parameters
    ----------
    config_dir : pathlib.Path
        Directory containing the experiment configuration files.

    Returns
    -------
    int
        Process-style return code. A value of ``0`` indicates that the YAML
        file was rendered successfully.

    Raises
    ------
    FileNotFoundError
        If a required YAML configuration file is missing.
    KeyError
        If a required configuration key is missing.
    TypeError
        If a loaded YAML file has an invalid top-level structure.

    Notes
    -----
    This command writes the rendered YAML into the configured rendered output
    directory. It does not submit or execute the MPAS-JEDI application.

    See Also
    --------
    write_rendered_yaml : Render and write the application YAML file.
    run_render_pbs : Render the matching PBS submission script.

    Examples
    --------
    >>> from pathlib import Path
    >>> # run_render_yaml(Path("configs/experiments/3dfgat_mpastatic_x1.10242_2018041500"))
    >>> Path("experiment.yaml").suffix
    '.yaml'
    """
    cfg = load_experiment_config(config_dir)
    path = write_rendered_yaml(cfg)
    print(f"[OK] rendered YAML: {path}")
    return 0


def run_render_pbs(config_dir: Path) -> int:
    """Render the PBS submission script for the experiment.

    Parameters
    ----------
    config_dir : pathlib.Path
        Directory containing the split YAML configuration files.

    Returns
    -------
    int
        Process-style return code. A value of ``0`` indicates that the PBS
        script was rendered successfully.

    Raises
    ------
    FileNotFoundError
        If a required YAML configuration file is missing.
    KeyError
        If a required configuration key is missing.
    TypeError
        If a loaded YAML file has an invalid top-level structure.

    Notes
    -----
    The generated PBS file is made executable by ``write_rendered_pbs``. This
    command only renders the submission script; it does not call ``qsub``.

    See Also
    --------
    write_rendered_pbs : Render and write an executable PBS script.
    run_render_yaml : Render the application YAML consumed by the PBS script.

    Examples
    --------
    >>> from pathlib import Path
    >>> # run_render_pbs(Path("configs/experiments/3dfgat_mpastatic_x1.10242_2018041500"))
    >>> Path("job.pbs").suffix
    '.pbs'
    """
    cfg = load_experiment_config(config_dir)
    path = write_rendered_pbs(cfg)
    print(f"[OK] rendered PBS: {path}")
    return 0


def main() -> int:
    """Execute the command-line entry point.

    Parameters
    ----------
    None

    Returns
    -------
    int
        Process-style return code returned by the selected subcommand. The
        value is ``2`` when argument parsing reaches an unsupported command.

    Raises
    ------
    SystemExit
        Raised by ``argparse`` when invalid command-line arguments are passed.
    FileNotFoundError
        Propagated from subcommands when required input files are missing.
    KeyError
        Propagated from subcommands when required configuration keys are
        missing.
    TypeError
        Propagated from subcommands when configuration structures are invalid.
    ValueError
        Propagated from subcommands when validation fails.

    Notes
    -----
    This function is intentionally thin. The command dispatch table is kept
    explicit so that each command maps to a clearly named function that can be
    tested independently.

    See Also
    --------
    build_parser : Construct the command-line parser.
    run_validate : Handle ``validate-config``.
    run_prepare : Handle ``prepare-runtime``.
    run_render_yaml : Handle ``render-yaml``.
    run_render_pbs : Handle ``render-pbs``.

    Examples
    --------
    >>> callable(main)
    True
    """
    parser = build_parser()
    args = parser.parse_args()

    # Explicit dispatch makes command behavior easy to audit and avoids hidden
    # side effects that could be surprising in an operational HPC workflow.
    if args.command == "validate-config":
        return run_validate(args.config_dir)

    if args.command == "prepare-runtime":
        return run_prepare(args.config_dir)

    if args.command == "render-yaml":
        return run_render_yaml(args.config_dir)

    if args.command == "render-pbs":
        return run_render_pbs(args.config_dir)

    parser.error("invalid command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
