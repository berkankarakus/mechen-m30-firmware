#!/usr/bin/env bash
# Decompile the resident MIPS16 key driver and verify its recovered event paths.
# Static analysis only: no firmware or device state is modified.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
DRIVER=${1:-$ROOT/analysis/community/fw/key.drv}
GHIDRA=${GHIDRA:-/opt/homebrew/Cellar/ghidra/12.2/libexec/support/analyzeHeadless}
JAVA_HOME_OVERRIDE=${JAVA_HOME_OVERRIDE:-/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home}

[ -f "$DRIVER" ] || { echo "missing key driver: $DRIVER" >&2; exit 1; }
[ -x "$GHIDRA" ] || { echo "missing Ghidra analyzeHeadless: $GHIDRA" >&2; exit 1; }

PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/key_binary_probe.py" "$DRIVER"

WORK=$(mktemp -d "${TMPDIR:-/private/tmp}/m30-ghidra-key.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/project"

# key.drv's resident payload starts at file 0x200 and is loaded at
# 0xbfc10000. FlatLoad's base is therefore the virtual address of file byte
# zero, 0xbfc0fe00.
set +e
JAVA_HOME_OVERRIDE="$JAVA_HOME_OVERRIDE" \
GHIDRA_JAVA_OPTIONS="${GHIDRA_JAVA_OPTIONS:--Duser.home=$WORK/home}" \
  "$GHIDRA" "$WORK/project" m30key \
  -import "$DRIVER" \
  -loader BinaryLoader \
  -processor 'MIPS:LE:32:default' \
  -noanalysis \
  -scriptPath "$ROOT/tools/ghidra" \
  -postScript FlatLoad.java "$DRIVER" 0xbfc0fe00 0x200 0xa00 \
  -postScript DumpAt.java \
    0xbfc10008,0xbfc10084,0xbfc10178,0xbfc101f4,0xbfc10220,0xbfc102e4,0xbfc103cc,0xbfc10508,0xbfc10518 \
    "$WORK/key.c" 2>&1 | tee "$WORK/ghidra.log"
STATUS=${PIPESTATUS[0]}
set -e
[ "$STATUS" -eq 0 ] || exit "$STATUS"

for address in bfc10008 bfc10084 bfc10178 bfc101f4 bfc10220 bfc102e4 bfc103cc bfc10508 bfc10518; do
  grep -q "DumpAt: $address -> FUN_$address" "$WORK/ghidra.log"
done
grep -q 'param_1 == 0x32' "$WORK/key.c"
grep -q 'param_1 == 0x34' "$WORK/key.c"
grep -q '0x1000' "$WORK/key.c"
grep -q '0x800' "$WORK/key.c"
grep -q 'FUN_bfc103cc' "$WORK/key.c"
echo 'KEY DRIVER PASS functions=9 adc-classifier=0xbfc10178 repeat-events=0x1000,0x800'
