#!/usr/bin/env bash
#
# Stage a GPSRO BUFR basename expected by obs2ioda_v3 and run the converter.
#
set -euo pipefail

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
    *)
      echo "ERROR: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

[[ -x "${executable}" ]] || { echo "ERROR: executable is unavailable: ${executable}" >&2; exit 2; }
[[ -r "${input}" ]] || { echo "ERROR: GPSRO input is unreadable: ${input}" >&2; exit 2; }

input_realpath="$(readlink -f "${input}")"
target="$(basename "${input}")"

if [[ -e "${target}" || -L "${target}" ]]; then
  if [[ ! -L "${target}" || "$(readlink -f "${target}")" != "${input_realpath}" ]]; then
    echo "ERROR: refusing to replace existing ${target}; use a clean cycle work directory" >&2
    exit 2
  fi
else
  ln -s "${input_realpath}" "${target}"
fi

exec "${executable}" "${target}"
