#!/usr/bin/env bash
# Environment modules for JACI.
#
# This file prepares the runtime environment used by MONAN-JEDI-WORKFLOW
# validation scripts and PBS jobs. It first loads the MONAN-JEDI stack runtime
# when requested by site.env, then loads the Python runtime used by repository
# helper scripts.

# JACI site-provided shell functions may reference variables that are unset when
# repository scripts run with `set -u`. Temporarily disable nounset while loading
# modules and starting Conda, then restore the previous shell option state before
# returning to the caller.
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

monan_load_python_runtime() {
  if [[ "${MONAN_LOAD_ANACONDA:-true}" != "true" ]]; then
    printf '[INFO] MONAN_LOAD_ANACONDA is not true; skipping Anaconda setup.\n'
    return 0
  fi

  module load anaconda

  if command -v start_conda >/dev/null 2>&1; then
    # Clear positional parameters before calling start_conda. On JACI, start_conda
    # may treat inherited positional arguments as a Conda environment path.
    set --
    start_conda
  else
    printf '[WARN] start_conda command not available after loading anaconda.\n' >&2
  fi
}

if command -v module >/dev/null 2>&1; then
  monan_load_stack_runtime || monan_modules_die "failed to load MONAN-JEDI stack runtime"
  monan_load_python_runtime || monan_modules_die "failed to load JACI Python runtime"
else
  printf '[WARN] module command not available; skipping module setup.\n' >&2
fi

if [[ "${monan_had_nounset}" == "1" ]]; then
  set -u
else
  set +u
fi
unset monan_had_nounset

if command -v python3 >/dev/null 2>&1; then
  printf '[INFO] Python3 runtime: %s\n' "$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  printf '[INFO] Python runtime: %s\n' "$(command -v python)"
else
  printf '[ERROR] Python is not available after JACI module setup.\n' >&2
  return 1 2>/dev/null || exit 1
fi

if [[ -n "${MPI_LAUNCHER:-}" ]]; then
  if command -v "${MPI_LAUNCHER}" >/dev/null 2>&1; then
    printf '[INFO] MPI launcher: %s\n' "$(command -v "${MPI_LAUNCHER}")"
  else
    printf '[WARN] MPI launcher not found after JACI module setup: %s\n' "${MPI_LAUNCHER}" >&2
  fi
fi

unset -f monan_modules_die monan_load_stack_runtime monan_load_python_runtime
