"""Public standalone commands installed by the monan-jedi-workflow package.

These are independent CLI entry points, not subcommands of a wrapper binary.
The existing domain app and scientific PBS implementations remain unchanged.
"""
from __future__ import annotations

import sys


def experiment() -> int:
    from .unified_cli import _experiment
    return _experiment(list(sys.argv[1:]))


def wps() -> int:
    from .cli_frontend import main
    args = list(sys.argv[1:])
    if not args or args[0] not in {"prepare", "run", "validate"}:
        print("Usage: wps {prepare|run|validate} CONFIG_DIR --cycle UTC", file=sys.stderr)
        return 2
    return main(["wps-" + args[0], *args[1:]])


def diagnostic() -> int:
    from .platform_cli import main
    return main("diagnostics", list(sys.argv[1:]))


def diagnose() -> int:
    from .diagnostics import main
    return main(list(sys.argv[1:]))
