#!/usr/bin/env python3
"""Basic SABER input validation for MONAN/JEDI 3DVar-FGAT."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import yaml


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def expand(value: str) -> str:
    return os.path.expandvars(value)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate SABER input paths.")
    parser.add_argument("--render-context", type=Path, default=Path("configs/experiments/3dvar_fgat/render_context.example.yaml"))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    data = read_yaml(args.render_context)
    jedi = data.get("jedi", {}) if isinstance(data, dict) else {}
    if not isinstance(jedi, dict):
        print("[ERROR] render context has no jedi mapping")
        return 2

    paths = {
        "stddev_file": expand(str(jedi.get("bump_cov_stddev_file", ""))),
        "nicas_dir": expand(str(jedi.get("bump_cov_dir", ""))),
        "vbal_dir": expand(str(jedi.get("bump_cov_vbal_dir", ""))),
    }

    ok = True
    for label, value in paths.items():
        path = Path(value)
        print(f"[INFO] {label}: {path}")
        if not value or "$" in value:
            level = "ERROR" if args.strict else "WARN"
            print(f"[{level}] unresolved path for {label}: {value}")
            ok = False if args.strict else ok
            continue
        if not path.exists():
            level = "ERROR" if args.strict else "WARN"
            print(f"[{level}] missing {label}: {path}")
            ok = False if args.strict else ok

    if not ok:
        return 2
    print("[INFO] SABER input validation completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
