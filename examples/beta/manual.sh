#!/usr/bin/env bash
# Smoke test of ONE synthetic cycle. NOT a scientific MPAS/JEDI validation.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Uso: bash manual.sh experiment.yaml AAAA-MM-DDTHH:MM:SSZ" >&2
  exit 2
fi
config="$1"
cycle="$2"
log="$(pwd)/manual-test.log"
: > "$log"

steps=0
fail() {
  local label="$1"
  echo "[FALHA] $label" >&2
  echo "O teste foi interrompido. Consulte: $log" >&2
  echo "Ultimas linhas do log:" >&2
  tail -n 25 "$log" >&2
  exit 1
}

run_step() {
  local label="$1"
  shift
  printf '%s\n' "\$ $*" >> "$log"
  if ! "$@" >> "$log" 2>&1; then
    fail "$label"
  fi
}

check_status() {
  local label="$1"
  shift
  local output
  printf '%s\n' "\$ $* status $config --cycle $cycle --json" >> "$log"
  if ! output=$("$@" status "$config" --cycle "$cycle" --json" 2>> "$log"); then
    fail "$label: status"
  fi
  printf '%s\n' "$output" >> "$log"
  if ! printf '%s\n' "$output" | python -c '
import json, sys
try:
    state = json.load(sys.stdin)
except (ValueError, TypeError):
    sys.exit(1)
sys.exit(0 if state.get("state") == "validated" and
    state.get("configuration_compatible", True) is True else 1)
'; then
    fail "$label: estado final nao validado"
  fi
}

test_app() {
  local label="$1"
  shift
  for action in prepare run validate; do
    run_step "$label: $action" "$@" "$action" "$config" --cycle "$cycle"
  done
  check_status "$label" "$@"
  steps=$((steps + 1))
  printf '[OK] %s — prepare / run / validate / status\n' "$label"
}

echo "MONAN-JEDI | teste de instalacao (dados artificiais)"
echo "Ciclo: $cycle"
echo

test_app "OBS — aquisicao" obs acquire
test_app "OBS — conversao IODA" obs convert
test_app "JEDI — assimilacao" jedi
test_app "MPAS — previsao" mpas
test_app "DIAGNOSTICS — diagnosticos" diagnostics

echo
echo "==========================================="
echo " TODOS OS $steps TESTES PASSARAM"
echo " Instalacao e contratos basicos: OK"
echo " ATENCAO: produtos artificiais; NAO"
echo "          valida execucao cientifica real."
echo " Log completo: $log"
echo "==========================================="
