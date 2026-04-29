#!/usr/bin/env bash
# Environment modules for JACI.
#
# This file prepares the Python runtime used by MONAN-JEDI-WORKFLOW validation
# and PBS jobs. It follows the same JACI pattern used by the
# kalman_soil_assimilation project: load the Anaconda module and initialize
# Conda with start_conda.

# JACI site-provided shell functions may reference variables that are unset when
# repository scripts run with `set -u`. Temporarily disable nounset while loading
# modules and starting Conda, then restore it before returning to the caller.
set +u

if command -v module >/dev/null 2>&1; then
  module load anaconda
else
  printf '[WARN] module command not available; skipping Anaconda module setup.\n' >&2
fi

if command -v start_conda >/dev/null 2>&1; then
  # Clear positional parameters before calling start_conda. On JACI, start_conda
  # may treat inherited positional arguments as a Conda environment path.
  set --
  start_conda
else
  printf '[WARN] start_conda command not available after loading anaconda.\n' >&2
fi

set -u

if command -v python3 >/dev/null 2>&1; then
  printf '[INFO] Python3 runtime: %s\n' "$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  printf '[INFO] Python runtime: %s\n' "$(command -v python)"
else
  printf '[ERROR] Python is not available after JACI module setup.\n' >&2
  return 1 2>/dev/null || exit 1
fi
