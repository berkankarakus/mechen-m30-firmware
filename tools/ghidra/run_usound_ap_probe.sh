#!/usr/bin/env bash
# Prove the usound AP's conditional driver-install call. Static only.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
AP=${1:-$ROOT/analysis/community/fw/usound.ap}
GHIDRA=${GHIDRA:-/opt/homebrew/Cellar/ghidra/12.2/libexec/support/analyzeHeadless}
JAVA_HOME_OVERRIDE=${JAVA_HOME_OVERRIDE:-/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home}

[ -f "$AP" ] || { echo "missing usound AP: $AP" >&2; exit 1; }
[ -x "$GHIDRA" ] || { echo "missing Ghidra analyzeHeadless: $GHIDRA" >&2; exit 1; }

PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/usound_ap_binary_probe.py" "$AP"

WORK=$(mktemp -d "${TMPDIR:-/private/tmp}/m30-ghidra-usound-ap.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/project"

set +e
JAVA_HOME_OVERRIDE="$JAVA_HOME_OVERRIDE" \
GHIDRA_JAVA_OPTIONS="${GHIDRA_JAVA_OPTIONS:--Duser.home=$WORK/home}" \
  "$GHIDRA" "$WORK/project" m30usoundap \
  -import "$AP" \
  -loader BinaryLoader \
  -processor 'MIPS:LE:32:default' \
  -noanalysis \
  -scriptPath "$ROOT/tools/ghidra" \
  -postScript LoadAP.java "$AP" \
  -postScript DumpAt.java 0x40094e88 "$WORK/app.c" 2>&1 | tee "$WORK/ghidra.log"
STATUS=${PIPESTATUS[0]}
set -e
[ "$STATUS" -eq 0 ] || exit "$STATUS"

grep -q 'LoadAP: blocks=15 prologue functions=87 entry=40014c30' "$WORK/ghidra.log"
grep -q 'DumpAt: 40094e88 -> FUN_40094e88' "$WORK/ghidra.log"
grep -Fq '(*_UNK_40095064)(&UNK_40095014,0,0,0);' "$WORK/app.c"
grep -Fq '(*_UNK_40095064)(&UNK_40095020,1,0,0);' "$WORK/app.c"
grep -Fq 'iVar1 = (*_UNK_4009505c)(5,0,&UNK_4009502c,10);' "$WORK/app.c"
grep -Fq '(*_UNK_4009505c)(&UNK_40095038,0,0,0x4b);' "$WORK/app.c"
echo 'USOUND AP DRIVER PATH PASS app=0x40094e88 driver-name=0x4009502c install-error=0x40095038'
