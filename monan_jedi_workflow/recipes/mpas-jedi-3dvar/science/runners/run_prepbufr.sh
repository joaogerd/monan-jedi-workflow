#!/usr/bin/env bash
#
# Run the MONAN-JEDI obs2ioda_v3 PREPBUFR reader in its required working layout.
#
# The tested executable reads a fixed basename, ./prepbufr.bufr, and writes
# IODA files in the current working directory. This wrapper is intentionally
# executed by monan-jedi-workflow with the cycle work directory as cwd.
#
# Usage:
#   run_prepbufr.sh --executable PATH --input PREPBUFR
#
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: run_prepbufr.sh --executable PATH --input PREPBUFR

Create or verify ./prepbufr.bufr as a symlink to PREPBUFR, then execute the
configured obs2ioda_v3 binary in the current directory.
EOF
}

executable=""
input=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --executable)
      [[ $# -ge 2 ]] || { echo "ERROR: --executable requires a value" >&2; exit 2; }
      executable="$2"
      shift 2
      ;;
    --input)
      [[ $# -ge 2 ]] || { echo "ERROR: --input requires a value" >&2; exit 2; }
      input="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[[ -n "${executable}" ]] || { echo "ERROR: --executable is required" >&2; exit 2; }
[[ -n "${input}" ]] || { echo "ERROR: --input is required" >&2; exit 2; }
[[ -x "${executable}" ]] || { echo "ERROR: executable is unavailable: ${executable}" >&2; exit 2; }
[[ -r "${input}" ]] || { echo "ERROR: PREPBUFR input is unreadable: ${input}" >&2; exit 2; }

input_realpath="$(readlink -f "${input}")"
target="prepbufr.bufr"

if [[ -e "${target}" || -L "${target}" ]]; then
  if [[ -L "${target}" ]] && [[ "$(readlink -f "${target}")" == "${input_realpath}" ]]; then
    :
  else
    echo "ERROR: refusing to replace existing ${target}; use a clean cycle work directory" >&2
    exit 2
  fi
else
  ln -s "${input_realpath}" "${target}"
fi

exec "${executable}"
