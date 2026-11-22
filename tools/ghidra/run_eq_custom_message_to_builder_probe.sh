#!/usr/bin/env bash
# Execute the music Custom callback, pass its captured output to MEngine's real
# 0x303 dispatcher, then verify the real EQ builder's seven-band structure.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
MUSIC=${1:-$ROOT/analysis/community/fw/music.ap}
MENGINE=${2:-$ROOT/analysis/community/fw/mengine.ap}
GHIDRA=${GHIDRA:-/opt/homebrew/Cellar/ghidra/12.2/libexec/support/analyzeHeadless}
EXPECTED_MENGINE_SHA256=b569605e9f66ef94023cf82d665ae119f6bbb7ed0c9d8f5e6c5be867ce91be49

[ -f "$MUSIC" ] || { echo "missing community music.ap: $MUSIC" >&2; exit 1; }
[ -f "$MENGINE" ] || { echo "missing community mengine.ap: $MENGINE" >&2; exit 1; }
[ -x "$GHIDRA" ] || { echo "missing Ghidra analyzeHeadless: $GHIDRA" >&2; exit 1; }
actual_sha256=$(shasum -a 256 "$MENGINE" | awk '{print $1}')
[ "$actual_sha256" = "$EXPECTED_MENGINE_SHA256" ] || {
  echo "mengine.ap SHA-256 $actual_sha256 != $EXPECTED_MENGINE_SHA256" >&2
  exit 1
}

WORK=$(mktemp -d "${TMPDIR:-/private/tmp}/m30-eq-custom-to-builder.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/home" "$WORK/project"
CAPTURE="$WORK/music-custom-output.bin"

bash "$ROOT/tools/ghidra/run_eq_custom_framework_callback_probe.sh" \
  "$MUSIC" "$CAPTURE" >"$WORK/music.log"
grep -F 'EQ CUSTOM FRAMEWORK CALLBACK PASS ' "$WORK/music.log"
[ "$(wc -c < "$CAPTURE" | tr -d ' ')" = 11 ] || {
  echo "music callback capture must be 11 bytes (4 message + 7 Custom gains)" >&2
  exit 1
}

GHIDRA_JAVA_OPTIONS="${GHIDRA_JAVA_OPTIONS:--Duser.home=$WORK/home}" \
  "$GHIDRA" "$WORK/project" m30eqcustomdelivery \
    -import "$MENGINE" \
    -loader BinaryLoader \
    -processor 'MIPS:LE:32:default' \
    -noanalysis \
    -scriptPath "$ROOT/tools/ghidra" \
    -postScript LoadAP.java "$MENGINE" \
    -postScript RunEqCustomMengineDeliveryProbe.java "$CAPTURE" \
    >"$WORK/mengine.log" 2>&1 || {
      cat "$WORK/mengine.log" >&2
      exit 1
    }

if ! grep -Fq 'EQ CUSTOM MESSAGE-TO-BUILDER PASS ' "$WORK/mengine.log"; then
  cat "$WORK/mengine.log" >&2
  echo "MEngine custom-message probe did not report PASS" >&2
  exit 1
fi
grep -F 'EQ CUSTOM MESSAGE-TO-BUILDER PASS ' "$WORK/mengine.log"
