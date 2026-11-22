#!/usr/bin/env bash
# Execute Custom-row registration through its real deferred-callback dispatcher.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
MUSIC=${1:-$ROOT/analysis/community/fw/music.ap}
GHIDRA=${GHIDRA:-/opt/homebrew/Cellar/ghidra/12.2/libexec/support/analyzeHeadless}
EXPECTED_SHA256=662e379602707a9c4b0dcd6b94b591dd77c2b5f7a557fcb03b8c2a5c9b1baac3

[ -f "$MUSIC" ] || { echo "missing community music.ap: $MUSIC" >&2; exit 1; }
[ -x "$GHIDRA" ] || { echo "missing Ghidra analyzeHeadless: $GHIDRA" >&2; exit 1; }
actual_sha256=$(shasum -a 256 "$MUSIC" | awk '{print $1}')
[ "$actual_sha256" = "$EXPECTED_SHA256" ] || {
  echo "music.ap SHA-256 $actual_sha256 != $EXPECTED_SHA256" >&2
  exit 1
}

WORK=$(mktemp -d "${TMPDIR:-/private/tmp}/m30-ghidra-eq-custom-framework.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/home" "$WORK/project"

GHIDRA_JAVA_OPTIONS="${GHIDRA_JAVA_OPTIONS:--Duser.home=$WORK/home}" \
  "$GHIDRA" "$WORK/project" m30eqcustomframework \
    -import "$MUSIC" \
    -loader BinaryLoader \
    -processor 'MIPS:LE:32:default' \
    -noanalysis \
    -scriptPath "$ROOT/tools/ghidra" \
    -postScript LoadAP.java "$MUSIC" \
    -postScript RunEqCustomFrameworkCallbackProbe.java \
    >"$WORK/run.log" 2>&1 || {
      cat "$WORK/run.log" >&2
      exit 1
    }

if ! grep -Fq 'EQ CUSTOM FRAMEWORK CALLBACK PASS ' "$WORK/run.log"; then
  cat "$WORK/run.log" >&2
  echo "Ghidra completed without the expected framework-dispatched callback marker" >&2
  exit 1
fi
grep -F 'EQ CUSTOM FRAMEWORK CALLBACK PASS ' "$WORK/run.log"
