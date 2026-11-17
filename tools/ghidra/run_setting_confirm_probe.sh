#!/usr/bin/env bash
# Execute the setting.ap confirmation path until its 0x100a UI request.
# UI functions are intercepted; this does not flash or modify device data.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
AP=${1:-$ROOT/analysis/community/fw/setting.ap}
INPUT=${2:-1}
GHIDRA=${GHIDRA:-/opt/homebrew/Cellar/ghidra/12.2/libexec/support/analyzeHeadless}
JAVA_HOME_OVERRIDE=${JAVA_HOME_OVERRIDE:-${JAVA_HOME:-}}
WORK=$(mktemp -d "${TMPDIR:-/private/tmp}/m30-ghidra-setting-confirm.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

[ -f "$AP" ] || { echo "missing setting AP: $AP" >&2; exit 1; }
[ -x "$GHIDRA" ] || { echo "missing Ghidra analyzeHeadless: $GHIDRA" >&2; exit 1; }
if [ -n "$JAVA_HOME_OVERRIDE" ]; then
  export JAVA_HOME="$JAVA_HOME_OVERRIDE"
fi
mkdir -p "$WORK/project" "$WORK/home"
LOG="$WORK/ghidra.log"

set +e
GHIDRA_JAVA_OPTIONS="-Duser.home=$WORK/home" \
  "$GHIDRA" "$WORK/project" m30settingconfirm \
    -import "$AP" \
    -loader BinaryLoader \
    -processor 'MIPS:LE:32:default' \
    -noanalysis \
    -scriptPath "$ROOT/tools/ghidra" \
    -postScript LoadAP.java "$AP" \
    -postScript RunSettingConfirmProbe.java "$INPUT" 2>&1 | tee "$LOG"
STATUS=${PIPESTATUS[0]}
set -e

[ "$STATUS" -eq 0 ] || exit "$STATUS"
if grep -q 'ERROR REPORT SCRIPT ERROR' "$LOG"; then
  echo "Ghidra script reported an error; probe is not considered a pass" >&2
  exit 1
fi
grep -q 'SETTING CONFIRM REQUEST PASS' "$LOG"
