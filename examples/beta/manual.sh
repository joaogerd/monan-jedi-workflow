#!/usr/bin/env bash
# User-written sequence for a SINGLE timestamp; no campaign loop.
set -euo pipefail
config="${1:?usage: bash manual.sh experiment.yaml CYCLE}"
cycle="${2:?specify UTC cycle}"
for action in prepare run validate; do obs acquire "$action" "$config" --cycle "$cycle"; done
for action in prepare run validate; do obs convert "$action" "$config" --cycle "$cycle"; done
for action in prepare run validate; do jedi "$action" "$config" --cycle "$cycle"; done
for action in prepare run validate; do mpas "$action" "$config" --cycle "$cycle"; done
for action in prepare run validate; do diagnostics "$action" "$config" --cycle "$cycle"; done
