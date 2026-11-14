#!/usr/bin/env bash
# Decompile the three bank-qualified candidates referenced by the B3 tail.
# Static analysis only; this does not execute or modify firmware.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
DRIVER=${1:-$ROOT/analysis/community/fw/drv_ui.drv}
GHIDRA=${GHIDRA:-/opt/homebrew/Cellar/ghidra/12.2/libexec/support/analyzeHeadless}
JAVA_HOME_OVERRIDE=${JAVA_HOME_OVERRIDE:-/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home}

[ -f "$DRIVER" ] || { echo "missing driver: $DRIVER" >&2; exit 1; }
[ -x "$GHIDRA" ] || { echo "missing Ghidra analyzeHeadless: $GHIDRA" >&2; exit 1; }

# The public runtime formula maps each bank to a 0x800-byte window.  Include
# the 0x800-byte post-bank area as well: the candidate functions use literal
# pools immediately after their nominal bank window.
WORK=$(mktemp -d "${TMPDIR:-/private/tmp}/m30-ghidra-b3-candidates.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/project"

set +e
JAVA_HOME_OVERRIDE="$JAVA_HOME_OVERRIDE" \
GHIDRA_JAVA_OPTIONS="${GHIDRA_JAVA_OPTIONS:--Duser.home=$WORK/home}" \
  "$GHIDRA" "$WORK/project" m30b3candidates \
  -import "$DRIVER" \
  -loader BinaryLoader \
  -processor 'MIPS:LE:32:default' \
  -noanalysis \
  -scriptPath "$ROOT/tools/ghidra" \
  -postScript MapSegments.java 3 \
    "$DRIVER" 0x2611a980 0xa674 0x100c 1 \
    "$DRIVER" 0x261d7980 0xd674 0x100c 1 \
    "$DRIVER" 0x26216980 0xe674 0x100c 1 \
  -postScript DumpAt.java 0x26125750,0x261e5694,0x26225400 "$WORK/decomp.c" \
  2>&1 | tee "$WORK/ghidra.log"
STATUS=${PIPESTATUS[0]}
set -e
[ "$STATUS" -eq 0 ] || exit "$STATUS"

grep -q 'DumpAt: 26125750 -> FUN_26125750' "$WORK/ghidra.log"
grep -q 'DumpAt: 261e5694 -> FUN_261e5694' "$WORK/ghidra.log"
grep -q 'DumpAt: 26225400 -> FUN_26225400' "$WORK/ghidra.log"
grep -q 'void FUN_26125750' "$WORK/decomp.c"
grep -q 'ushort FUN_261e5694' "$WORK/decomp.c"
grep -q 'void FUN_26225400(void)' "$WORK/decomp.c"

echo 'DRV_UI B3 CANDIDATES PASS B04=0x26125750 B07=0x261e5694 B08=0x26225400'
