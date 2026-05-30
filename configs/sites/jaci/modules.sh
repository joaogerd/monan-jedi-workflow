#!/usr/bin/env bash
# Environment modules for JACI.
#
# This file prepares the runtime environment used by MONAN-JEDI-WORKFLOW
# validation scripts and PBS jobs. It loads the MONAN-JEDI stack runtime and then
# validates that the active Python interpreter is the Python provided by that
# stack. Do not load Anaconda here: the JACI stack Python packages are built for
# CPython 3.11, while the site Anaconda module may provide a different Python ABI.

# JACI site-provided shell functions may reference variables that are unset when
# repository scripts run with `set -u`. Temporarily disable nounset while loading
# modules, then restore the previous shell option state before returning to the
# caller.
case "$-" in
  *u*) monan_had_nounset=1 ;;
  *) monan_had_nounset=0 ;;
esac

set +u

monan_modules_die() {
  printf '[ERROR] %s\n' "$*" >&2
  return 1 2>/dev/null || exit 1
}

monan_load_stack_runtime() {
  if [[ "${MONAN_LOAD_STACK:-false}" != "true" ]]; then
    printf '[INFO] MONAN_LOAD_STACK is not true; skipping MONAN-JEDI stack runtime setup.\n'
    return 0
  fi

  : "${STACK_ROOT:?STACK_ROOT is required when MONAN_LOAD_STACK=true}"
  : "${STACK_ENV_NAME:?STACK_ENV_NAME is required when MONAN_LOAD_STACK=true}"
  : "${STACK_MODULE_ROOT:?STACK_MODULE_ROOT is required when MONAN_LOAD_STACK=true}"
  : "${STACK_ENV_MODULE:?STACK_ENV_MODULE is required when MONAN_LOAD_STACK=true}"

  local stack_site_setup="${STACK_SITE_SETUP:-${STACK_ROOT}/configs/sites/tier2/jaci/setup.sh}"
  local previous_dir
  previous_dir="$(pwd)"

  [[ -d "${STACK_ROOT}" ]] || monan_modules_die "STACK_ROOT not found: ${STACK_ROOT}"
  [[ -d "${STACK_MODULE_ROOT}" ]] || monan_modules_die "STACK_MODULE_ROOT not found: ${STACK_MODULE_ROOT}"
  [[ -f "${stack_site_setup}" ]] || monan_modules_die "STACK_SITE_SETUP not found: ${stack_site_setup}"

  printf '[INFO] Loading MONAN-JEDI stack site setup: %s\n' "${stack_site_setup}"
  cd "${STACK_ROOT}" || return 1
  # shellcheck disable=SC1090
  source "${stack_site_setup}"

  printf '[INFO] Using MONAN-JEDI stack module root: %s\n' "${STACK_MODULE_ROOT}"
  module use "${STACK_MODULE_ROOT}"

  printf '[INFO] Loading MONAN-JEDI stack environment module: %s\n' "${STACK_ENV_MODULE}"
  module load "${STACK_ENV_MODULE}"

  cd "${previous_dir}" || return 1

  printf '[INFO] MONAN-JEDI stack runtime loaded.\n'
}

monan_unload_conflicting_python_runtime() {
  # The site Anaconda module overrides python3 with Python 3.12 on JACI. That is
  # incompatible with the current stack modules, whose compiled Python packages
  # live under lib/python3.11/site-packages and expose CPython 3.11 extensions.
  if command -v module >/dev/null 2>&1; then
    module unload anaconda/24.1.2 >/dev/null 2>&1 || true
    module unload anaconda >/dev/null 2>&1 || true
  fi

  hash -r 2>/dev/null || true
}

monan_validate_python_runtime() {
  local python_exe
  local python_version

  if ! command -v python3 >/dev/null 2>&1; then
    monan_modules_die "python3 is not available after JACI module setup"
  fi

  python_exe="$(command -v python3)"
  python_version="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" || return 1

  printf '[INFO] Python3 runtime: %s\n' "${python_exe}"
  printf '[INFO] Python3 ABI: %s\n' "${python_version}"

  if [[ "${python_exe}" == /p/app/anaconda/* ]]; then
    monan_modules_die "Anaconda Python is active (${python_exe}); unload Anaconda and use the Spack stack Python"
  fi

  if [[ "${MONAN_LOAD_STACK:-false}" == "true" && "${python_version}" != "3.11" ]]; then
    monan_modules_die "wrong Python ABI (${python_version}); this JACI stack was built for Python 3.11"
  fi
}

if command -v module >/dev/null 2>&1; then
  monan_load_stack_runtime || monan_modules_die "failed to load MONAN-JEDI stack runtime"
  monan_unload_conflicting_python_runtime || monan_modules_die "failed to unload conflicting Python runtime"
  monan_validate_python_runtime || monan_modules_die "failed to validate JACI Python runtime"
else
  printf '[WARN] module command not available; skipping module setup.\n' >&2
fi

if [[ "${monan_had_nounset}" == "1" ]]; then
  set -u
else
  set +u
fi
unset monan_had_nounset

if [[ -n "${MPI_LAUNCHER:-}" ]]; then
  if command -v "${MPI_LAUNCHER}" >/dev/null 2>&1; then
    printf '[INFO] MPI launcher: %s\n' "$(command -v "${MPI_LAUNCHER}")"
  else
    printf '[WARN] MPI launcher not found after JACI module setup: %s\n' "${MPI_LAUNCHER}" >&2
  fi
fi

unset -f monan_modules_die monan_load_stack_runtime monan_unload_conflicting_python_runtime monan_validate_python_runtime
