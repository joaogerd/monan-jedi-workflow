from __future__ import annotations

import argparse
import json
from pathlib import Path

SUCCESS_MARKERS = (
    "Run: Finishing oops::Variational with status = 0",
    "OOPS Ending",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the MONAN-JEDI 3D-FGAT baseline log produced by simpleWorkflow."
    )
    parser.add_argument("--log", required=True, help="Path to the MPAS-JEDI execution log.")
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path where the validation summary JSON will be written.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    log_path = Path(args.log)
    output_path = Path(args.output_json)

    if not log_path.is_file():
        raise FileNotFoundError(f"Execution log not found: {log_path}")

    text = log_path.read_text(encoding="utf-8", errors="replace")
    missing = [marker for marker in SUCCESS_MARKERS if marker not in text]
    summary = {
        "log": str(log_path.resolve(strict=False)),
        "success": not missing,
        "required_markers": list(SUCCESS_MARKERS),
        "missing_markers": missing,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if missing:
        print(f"Missing success marker(s): {', '.join(missing)}")
        return 1
    print(f"Validation summary written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
