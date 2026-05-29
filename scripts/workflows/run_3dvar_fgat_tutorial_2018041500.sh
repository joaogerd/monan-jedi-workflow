#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/../.." && pwd)

cd "${REPO_ROOT}"

source scripts/utils/logging.sh

SITE_ENV="${SITE_ENV:-configs/sites/jaci/site.env}"
EXECUTE=false
SUBMIT_PBS=false
DRY_RUN=true
SKIP_SMOKE=false
CLEAN_RUNTIME=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --execute)
      EXECUTE=true
      DRY_RUN=false
      shift
      ;;
    --pbs)
      SUBMIT_PBS=true
      DRY_RUN=false
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --skip-smoke)
      SKIP_SMOKE=true
      shift
      ;;
    --clean-runtime)
      CLEAN_RUNTIME=true
      shift
      ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

PROVENANCE_DIR="${REPO_ROOT}/build/rendered/provenance"
WORKFLOW_TRACE="${PROVENANCE_DIR}/workflow.trace"
RENDER_TRACE="${PROVENANCE_DIR}/3dvar_fgat.trace"
RUNTIME_TRACE="${PROVENANCE_DIR}/runtime.trace"
VARIATIONAL_TRACE="${PROVENANCE_DIR}/variational.trace"
PBS_TRACE="${PROVENANCE_DIR}/3dvar_fgat_pbs.trace"
WORKFLOW_STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
WORKFLOW_STARTED_EPOCH="$(date -u +%s)"
WORKFLOW_GIT_COMMIT="$(git rev-parse HEAD 2>/dev/null || true)"
WORKFLOW_GIT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
WORKFLOW_STATUS="running"
WORKFLOW_STEP=0

mkdir -p "${PROVENANCE_DIR}"

write_workflow_trace_header() {
  cat > "${WORKFLOW_TRACE}" <<EOF
workflow:
  name: run_3dvar_fgat_tutorial_2018041500
  generated_by: scripts/workflows/run_3dvar_fgat_tutorial_2018041500.sh
  repository: ${REPO_ROOT}
  started_at_utc: ${WORKFLOW_STARTED_AT}
  git_branch: ${WORKFLOW_GIT_BRANCH:-unknown}
  git_commit: ${WORKFLOW_GIT_COMMIT:-unknown}
  site_env: ${SITE_ENV}
  options:
    execute: ${EXECUTE}
    submit_pbs: ${SUBMIT_PBS}
    dry_run: ${DRY_RUN}
    skip_smoke: ${SKIP_SMOKE}
    clean_runtime: ${CLEAN_RUNTIME}
  provenance_index:
    workflow_trace: build/rendered/provenance/workflow.trace
    render_trace: build/rendered/provenance/3dvar_fgat.trace
    runtime_trace: build/rendered/provenance/runtime.trace
    pbs_trace: build/rendered/provenance/3dvar_fgat_pbs.trace
    variational_trace: build/rendered/provenance/variational.trace
  expected_artifacts:
    rendered_yaml: build/rendered/3dvar_fgat.yaml
    rendered_observers: build/rendered/observers.yaml
    rendered_context: build/rendered/render_context.with_observers.yaml
    runtime_tree: build/runtime/jaci_3dvar_fgat_tutorial_2018041500/2018041500
    variational_command: build/rendered/mpasjedi_variational.command
    rendered_pbs: build/rendered/3dvar_fgat.pbs
  steps:
EOF
}

append_workflow_step() {
  local name="$1"
  local command="$2"
  local mode="${3:-required}"
  local trace="${4:-}"
  local produces="${5:-}"

  WORKFLOW_STEP=$((WORKFLOW_STEP + 1))
  cat >> "${WORKFLOW_TRACE}" <<EOF
    - step: ${WORKFLOW_STEP}
      name: ${name}
      command: ${command}
      mode: ${mode}
      started_at_utc: $(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

  if [[ -n "${trace}" ]]; then
    cat >> "${WORKFLOW_TRACE}" <<EOF
      trace: ${trace}
EOF
  fi

  if [[ -n "${produces}" ]]; then
    cat >> "${WORKFLOW_TRACE}" <<EOF
      produces: ${produces}
EOF
  fi
}

finalize_workflow_trace() {
  local exit_code=$?
  local finished_at
  local finished_epoch
  local duration_seconds
  finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  finished_epoch="$(date -u +%s)"
  duration_seconds=$((finished_epoch - WORKFLOW_STARTED_EPOCH))

  if [[ ${exit_code} -eq 0 ]]; then
    WORKFLOW_STATUS="completed"
  else
    WORKFLOW_STATUS="failed"
  fi

  cat >> "${WORKFLOW_TRACE}" <<EOF
  result:
    status: ${WORKFLOW_STATUS}
    exit_code: ${exit_code}
    finished_at_utc: ${finished_at}
    duration_seconds: ${duration_seconds}
EOF

  exit "${exit_code}"
}

trap finalize_workflow_trace EXIT
write_workflow_trace_header

log_info "Starting temporary Bash workflow for 3DVar-FGAT tutorial case"
log_info "Repository: ${REPO_ROOT}"
log_info "Site env: ${SITE_ENV}"
log_info "Workflow provenance trace: ${WORKFLOW_TRACE}"

append_workflow_step "load_site_environment" "source scripts/env/load_jaci_env.sh ${SITE_ENV}" "required" "" "environment variables and loaded modules"
source scripts/env/load_jaci_env.sh "${SITE_ENV}"

RUNTIME_DIR="${MONAN_WORKFLOW_ROOT}/build/runtime/jaci_3dvar_fgat_tutorial_2018041500/2018041500"

if [[ "${CLEAN_RUNTIME}" == true ]]; then
  append_workflow_step "clean_runtime" "rm -rf ${RUNTIME_DIR}" "optional" "" "clean runtime tree"
  log_warn "Removing runtime directory: ${RUNTIME_DIR}"
  rm -rf "${RUNTIME_DIR}"
fi

if [[ "${SKIP_SMOKE}" != true ]]; then
  append_workflow_step "smoke_checks" "bash tests/smoke_check.sh"
  log_info "Running smoke checks"
  bash tests/smoke_check.sh
else
  append_workflow_step "smoke_checks" "bash tests/smoke_check.sh" "skipped"
fi

append_workflow_step "render_jedi_yaml" "bash scripts/run/render_3dvar_fgat.sh" "required" "build/rendered/provenance/3dvar_fgat.trace" "build/rendered/3dvar_fgat.yaml"
log_info "Rendering JEDI YAML"
bash scripts/run/render_3dvar_fgat.sh

append_workflow_step "validate_window" "bash scripts/run/validate_3dvar_fgat_window.sh --strict"
log_info "Validating 3DVar-FGAT window"
bash scripts/run/validate_3dvar_fgat_window.sh --strict

append_workflow_step "validate_rendered_observers" "bash scripts/run/validate_3dvar_fgat_jedi_observers.sh --strict"
log_info "Validating rendered observers"
bash scripts/run/validate_3dvar_fgat_jedi_observers.sh --strict

append_workflow_step "validate_staged_inputs" "bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh"
log_info "Validating staged inputs"
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh

append_workflow_step "validate_file_formats" "bash scripts/setup/validate_3dvar_fgat_file_formats.sh --strict"
log_info "Validating file formats"
bash scripts/setup/validate_3dvar_fgat_file_formats.sh --strict

append_workflow_step "validate_mpas_background" "bash scripts/setup/validate_3dvar_fgat_mpas_background.sh --strict"
log_info "Validating MPAS background"
bash scripts/setup/validate_3dvar_fgat_mpas_background.sh --strict

append_workflow_step "validate_ioda_structure" "bash scripts/setup/validate_3dvar_fgat_ioda_structure.sh --strict"
log_info "Validating IODA structure"
bash scripts/setup/validate_3dvar_fgat_ioda_structure.sh --strict

append_workflow_step "validate_saber_bump_inputs" "bash scripts/setup/validate_3dvar_fgat_saber_inputs.sh --strict"
log_info "Validating SABER/BUMP inputs"
bash scripts/setup/validate_3dvar_fgat_saber_inputs.sh --strict

append_workflow_step "prepare_runtime" "bash scripts/run/prepare_3dvar_fgat_runtime.sh --strict" "required" "build/rendered/provenance/runtime.trace" "build/runtime/jaci_3dvar_fgat_tutorial_2018041500/2018041500"
log_info "Preparing runtime"
bash scripts/run/prepare_3dvar_fgat_runtime.sh --strict

if [[ "${EXECUTE}" == true ]]; then
  append_workflow_step "run_variational" "bash scripts/run/run_3dvar_fgat_variational.sh --execute" "execute" "build/rendered/provenance/variational.trace" "build/rendered/mpasjedi_variational.command and runtime logs"
  log_info "Preparing variational command and executing"
  bash scripts/run/run_3dvar_fgat_variational.sh --execute
else
  append_workflow_step "prepare_variational_command" "bash scripts/run/run_3dvar_fgat_variational.sh" "dry-run" "build/rendered/provenance/variational.trace" "build/rendered/mpasjedi_variational.command"
  log_info "Preparing variational command"
  bash scripts/run/run_3dvar_fgat_variational.sh
fi

if [[ "${SUBMIT_PBS}" == true ]]; then
  append_workflow_step "render_pbs_job" "bash scripts/run/render_3dvar_fgat_pbs.sh" "pbs" "build/rendered/provenance/3dvar_fgat_pbs.trace" "build/rendered/3dvar_fgat.pbs"
  log_info "Rendering PBS job"
  bash scripts/run/render_3dvar_fgat_pbs.sh

  PBS_FILE="${MONAN_WORKFLOW_ROOT}/build/rendered/3dvar_fgat.pbs"
  append_workflow_step "submit_pbs_job" "qsub ${PBS_FILE}" "pbs" "" "PBS job id"
  log_info "Submitting PBS job: ${PBS_FILE}"
  qsub "${PBS_FILE}"
else
  append_workflow_step "render_pbs_job" "bash scripts/run/render_3dvar_fgat_pbs.sh" "skipped" "build/rendered/provenance/3dvar_fgat_pbs.trace" "build/rendered/3dvar_fgat.pbs"
  append_workflow_step "submit_pbs_job" "qsub build/rendered/3dvar_fgat.pbs" "skipped"
fi

log_info "3DVar-FGAT temporary Bash workflow completed"
