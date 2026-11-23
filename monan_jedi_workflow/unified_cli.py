"""Single public CLI for MONAN scientific experiment workflows.

Domain modules remain independent; this CLI only dispatches to their existing
implementations. simpleWorkflow remains the scheduler/orchestration engine.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def _usage() -> int:
    print(
        "experiment — MONAN-JEDI campaign management\n\n"
        "  experiment create DEST --recipe NAME [--machine YAML | --site YAML] [--start UTC] [--duration P7D] [--resolution 240km] [--config YAML]\n"
        "  experiment recipes list|show NAME_OR_PATH\n"
        "  experiment check|export campaign.yaml\n"
        "  experiment validate|plan|run|status workflow.yaml\n"
        "  experiment suggest-dates [--case EXISTING_CASE]\n"
        "  experiment check-inputs CASE\n"
        "  experiment site init [--stack PATH] [--install PATH]\n"
        "  experiment site save     # preserve a proven environment\n"
        "  experiment machine validate PROFILE [--check-paths]\n"
        "  experiment machine show PROFILE\n\n"
        "Other independent commands: wps, obs, mpas, jedi, diagnostic, diagnose.\n"
        "Each command is installed by the monan-jedi-workflow package."
    )
    return 0

def _experiment(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help"}:
        return _usage()
    action, *args = argv
    if action == "machine":
        parser = argparse.ArgumentParser(prog="experiment machine")
        actions = parser.add_subparsers(dest="machine_action", required=True)
        validate = actions.add_parser("validate", help="validate a computational profile")
        validate.add_argument("profile", type=Path)
        validate.add_argument("--check-paths", action="store_true",
                              help="verify declared directories and module setup exist")
        show = actions.add_parser("show", help="print normalized computational profile")
        show.add_argument("profile", type=Path)
        try:
            opt = parser.parse_args(args)
            from .machine_profile import load_machine_profile
            profile = load_machine_profile(
                opt.profile, require_existing=bool(getattr(opt, "check_paths", False))
            )
        except (ValueError, OSError) as error:
            print(f"[ERRO] Perfil computacional invalido: {error}", file=sys.stderr)
            return 2
        if opt.machine_action == "show":
            import yaml
            print(yaml.safe_dump(profile.describe(), sort_keys=False), end="")
        else:
            print(f"[OK] Perfil computacional valido: {profile.name} ({profile.backend})")
        return 0
    if action == "recipes":
        from .recipe_config import BUILTIN, load_recipe
        if len(args) == 1 and args[0] == "list":
            print(BUILTIN)
            return 0
        if len(args) == 2 and args[0] == "show":
            import yaml
            _, descriptor = load_recipe(args[1])
            print(yaml.safe_dump(descriptor, sort_keys=False), end="")
            return 0
        print("Usage: experiment recipes list | show NAME_OR_PATH", file=sys.stderr)
        return 2
    if action == "site":
        from .experiment_environment import save_project_site, initialize_site
        parser = argparse.ArgumentParser(prog="experiment site")
        sub = parser.add_subparsers(dest="site_action", required=True)
        sub.add_parser("save", help="persist a verified environment from this shell")
        init = sub.add_parser("init", help="discover installed JACI runtime on first use")
        init.add_argument("--stack", type=Path, help="select installed spack-stack root")
        init.add_argument("--install", type=Path, help="select installed MONAN-JEDI prefix")
        try:
            options = parser.parse_args(args)
        except SystemExit as error:
            return int(error.code)
        try:
            if options.site_action == "init":
                target = initialize_site(
                    Path.cwd(), stack=options.stack, install=options.install
                )
            else:
                target = save_project_site(Path.cwd())
        except (ValueError, OSError) as error:
            print(f"[ERRO] {error}", file=sys.stderr)
            return 2
        print(f"[OK] Configuração permanente do site gravada: {target}")
        print("Novos experimentos neste workspace vão consumir esse site.yaml.")
        return 0
    if action in {"create", "start"}:
        parser = argparse.ArgumentParser(prog="experiment create")
        parser.add_argument("destination", type=Path)
        parser.add_argument("--recipe", default="mpas-jedi-3dvar",
                            help="Bundled recipe name or path to external recipe directory")
        parser.add_argument("--config", type=Path,
                            help="Optional YAML recipe overrides (CLI takes precedence)")
        parser.add_argument("--resolution", default=None)
        parser.add_argument("--levels", type=int, default=None)
        parser.add_argument("--cycle", default=None)
        parser.add_argument("--duration", default=None)
        parser.add_argument("--end", default=None, help="Inclusive final analysis UTC; conflicts with --duration")
        parser.add_argument("--observations", default=None,
                            help="Comma-separated observation groups, e.g. conv,gpsro")
        parser.add_argument("--mesh", default=None)
        parser.add_argument("--bmatrix", default=None)
        parser.add_argument("--timestep", type=int, default=None)
        parser.add_argument("--mode", choices=("cold", "warm"), default=None,
                            help="Cold start; warm start requires a validated model restart and is not implemented yet")
        parser.add_argument("--start", "--date", dest="start",
                            default="2025-09-01T00:00:00Z")
        parser.add_argument("--site", type=Path,
                            help="Persistent site YAML; otherwise read workspace/site.yaml")
        parser.add_argument("--machine", type=Path,
                            help="Explicit machine.yaml v1; PBS backend supported for scientific case creation")
        parser.add_argument("--workspace", type=Path,
                            help="Existing isolated site-profile directory; HPC paths remain unchanged")
        parser.add_argument("--pbs-queue", default=None)
        parser.add_argument("--pbs-walltime", default=None)
        parser.add_argument("--runtime-bin", type=Path)
        # The mode flag is intentionally omitted while scientific warm start
        # is unimplemented. Never silently interpret a warm request as cold.
        opt = parser.parse_args(args)
        from .experiment_start import create_experiment
        from .recipe_config import load_recipe, resolve_settings, select_science
        try:
            science, descriptor = load_recipe(opt.recipe)
            if opt.end is not None and opt.duration is not None:
                raise ValueError("--end and --duration are mutually exclusive")
            settings = resolve_settings(
                descriptor, config=opt.config, overrides={
                    "resolution": opt.resolution,
                    "levels": opt.levels,
                    "cycle": opt.cycle,
                    "duration": opt.duration,
                    "mode": opt.mode,
                    "observations": opt.observations.split(",") if opt.observations is not None else None,
                    "mesh": opt.mesh,
                    "bmatrix": opt.bmatrix,
                    "timestep": opt.timestep,
                }
            )
            if opt.end is not None:
                from .experiment_start import _utc_start, _duration
                step_hours = int(settings["cycle"][2:-1])
                begin = _utc_start(opt.start, step_hours=step_hours)
                finish = _utc_start(opt.end, step_hours=step_hours)
                if finish <= begin:
                    raise ValueError("--end must be later than --start")
                span = finish - begin
                hours = int(span.total_seconds() // 3600)
                _duration("PT" + str(hours) + "H", step_hours)
                settings["duration"] = "PT" + str(hours) + "H"
            settings["recipe"] = descriptor["name"]
            science = select_science(opt.recipe, settings, science)
            machine_profile = None
            if opt.machine is not None:
                if opt.site is not None or opt.workspace is not None:
                    raise ValueError("--machine cannot be combined with --site or --workspace")
                from .machine_profile import load_machine_profile, machine_to_legacy_site
                machine_profile = load_machine_profile(opt.machine, require_existing=True)
                # Fail before creating the destination for unsupported backends.
                machine_to_legacy_site(machine_profile)
            create_experiment(
                opt.destination, start=opt.start,
                pbs_queue=opt.pbs_queue,
                pbs_walltime=opt.pbs_walltime,
                runtime_bin=opt.runtime_bin, site_config=opt.site,
                workspace=opt.workspace, recipe_source=science,
                settings=settings, machine_profile=machine_profile,
            )
        except (ValueError, OSError) as error:
            print(f"[ERRO] Experimento não criado: {error}", file=sys.stderr)
            return 2
        print(f"[OK] Experimento configurado: {opt.destination.resolve()}")
        print("Próximo passo: source ./environment.sh; "
              "experiment check campaign.yaml")
        return 0
    if action in {"check", "export"}:
        return _domain("campaign", [action, *args])
    if action in {"validate", "plan", "run", "status"}:
        # Explicit proxy to the installed workflow engine. This does not
        # implement a second scheduler or hide any scientific PBS job.
        return _run_engine([action, *args])
    if action in {"suggest-dates", "check-inputs"}:
        if action == "check-inputs":
            parser = argparse.ArgumentParser(prog="experiment check-inputs")
            parser.add_argument("case", type=Path)
            opt = parser.parse_args(args)
            from .experiment_start import check_date_inputs
            try:
                results = check_date_inputs(opt.case)
            except (ValueError, OSError) as error:
                print(f"[ERRO] {error}", file=sys.stderr)
                return 2
            for label, path, present in results:
                print(f'[{"OK" if present else "MISSING"}] {label}: {path}')
            return 0 if all(ok for _, _, ok in results) else 2
        parser = argparse.ArgumentParser(prog="experiment suggest-dates")
        parser.add_argument("--case", type=Path, default=Path("."))
        opt = parser.parse_args(args)
        from .experiment_start import suggest_available_dates
        import os
        roots = (os.environ.get("MONAN_INPUT_ROOT"), os.environ.get("MONAN_GFS_ROOT"))
        if not all(roots):
            print("[ERRO] Source the experiment's environment.sh first.", file=sys.stderr)
            return 2
        dates = suggest_available_dates(input_root=roots[0], gfs_root=roots[1])
        for date in dates:
            print("[AVAILABLE] " + date)
        return 0 if dates else 2
    print(f"[ERRO] Unknown experiment command: {action}", file=sys.stderr)
    return 2


def _run_engine(argv: list[str]) -> int:
    try:
        completed = subprocess.run(["swf", *argv], check=False)
    except FileNotFoundError:
        print(
            "[ERRO] simpleWorkflow (swf) não está instalado. "
            "Instale o extra de orquestração do MONAN Workflow.",
            file=sys.stderr,
        )
        return 127
    return completed.returncode


def _domain(app: str, args: list[str]) -> int:
    from .platform_cli import main
    return main(app, args)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"--help", "-h", "help"}:
        return _usage()
    app, *rest = args
    if app == "experiment":
        return _experiment(rest)
    if app in {"obs", "mpas", "jedi", "diagnostic", "diagnostics", "campaign"}:
        return _domain("diagnostics" if app == "diagnostic" else app, rest)
    if app == "wps":
        if not rest or rest[0] not in {"prepare", "run", "validate"}:
            print("[ERRO] Use wps prepare|run|validate", file=sys.stderr)
            return 2
        from .cli_frontend import main as legacy_cli
        return legacy_cli(["wps-" + rest[0], *rest[1:]])
    if app == "diagnose":
        from .diagnostics import main as diagnosis_main
        return diagnosis_main(rest)
    print(f"[ERRO] Comando desconhecido: {app}. Use --help.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
