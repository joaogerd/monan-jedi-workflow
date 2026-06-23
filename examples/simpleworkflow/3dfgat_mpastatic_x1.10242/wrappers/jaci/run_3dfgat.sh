#!/usr/bin/env bash
set -euo pipefail

: "${MONAN_JEDI_EXECUTABLE:?Set MONAN_JEDI_EXECUTABLE to mpasjedi_variational.x}"
: "${MONAN_JEDI_YAML:?Set MONAN_JEDI_YAML to the rendered MPAS-JEDI YAML}"
: "${MONAN_JEDI_NP:=64}"
: "${MONAN_JEDI_LOG:=build/simpleworkflow/3dfgat_mpastatic_x1.10242_2018041500/logs/3dvar_fgat.log}"

if [[ -z "${PBS_JOBID:-}" && "${ALLOW_NON_PBS:-0}" != "1" ]]; then
  cat >&2 <<'MSG'
This wrapper is intended to run inside an allocated PBS job on JACI.
Submit or enter a PBS allocation first, then run simpleWorkflow from inside it.
Set ALLOW_NON_PBS=1 only for local smoke tests that do not execute MPAS-JEDI.
MSG
  exit 2
fi

if [[ ! -x "${MONAN_JEDI_EXECUTABLE}" ]]; then
  echo "MPAS-JEDI executable not found or not executable: ${MONAN_JEDI_EXECUTABLE}" >&2
  exit 2
fi

if [[ ! -f "${MONAN_JEDI_YAML}" ]]; then
  echo "Rendered MPAS-JEDI YAML not found: ${MONAN_JEDI_YAML}" >&2
  exit 2
fi

mkdir -p "$(dirname "${MONAN_JEDI_LOG}")"

{
  echo "[simpleWorkflow] job=${PBS_JOBID:-no-pbs}"
  echo "[simpleWorkflow] executable=${MONAN_JEDI_EXECUTABLE}"
  echo "[simpleWorkflow] yaml=${MONAN_JEDI_YAML}"
  echo "[simpleWorkflow] np=${MONAN_JEDI_NP}"
  echo "[simpleWorkflow] started=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} | tee "${MONAN_JEDI_LOG}"

mpirun -np "${MONAN_JEDI_NP}" "${MONAN_JEDI_EXECUTABLE}" "${MONAN_JEDI_YAML}" \
  >> "${MONAN_JEDI_LOG}" 2>&1
status=$?

echo "[simpleWorkflow] finished=$(date -u +%Y-%m-%dT%H:%M:%SZ) status=${status}" \
  | tee -a "${MONAN_JEDI_LOG}"
exit "${status}"
