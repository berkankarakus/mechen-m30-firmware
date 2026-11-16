#!/usr/bin/env bash
# Map a read-only ATJ2127 Boot ROM dump and decompile the two M30 candidate
# exception targets.  This never writes firmware or executes the dump.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
ROM=${1:-}
GHIDRA=${GHIDRA:-/opt/homebrew/Cellar/ghidra/12.2/libexec/support/analyzeHeadless}
JAVA_HOME_OVERRIDE=${JAVA_HOME_OVERRIDE:-/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home}

[ -n "$ROM" ] || { echo "usage: $0 ROM_DUMP" >&2; exit 2; }
[ -f "$ROM" ] || { echo "missing ROM dump: $ROM" >&2; exit 1; }
[ -x "$GHIDRA" ] || { echo "missing Ghidra analyzeHeadless: $GHIDRA" >&2; exit 1; }
[ "$(wc -c < "$ROM")" -eq $((0x40000)) ] || {
  echo "ROM dump must be exactly 0x40000 bytes" >&2
  exit 1
}

WORK=$(mktemp -d "${TMPDIR:-/private/tmp}/m30-ghidra-bootrom.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/project"

set +e
JAVA_HOME_OVERRIDE="$JAVA_HOME_OVERRIDE" \
GHIDRA_JAVA_OPTIONS="${GHIDRA_JAVA_OPTIONS:--Duser.home=$WORK/home}" \
  "$GHIDRA" "$WORK/project" m30bootrom \
  -import "$ROM" \
  -loader BinaryLoader \
  -processor 'MIPS:LE:32:default' \
  -noanalysis \
  -scriptPath "$ROOT/tools/ghidra" \
  -postScript MapSegments.java 1 "$ROM" 0x9fc00000 0 0x40000 0 \
  -postScript MarkFunction.java 0x9fc05f90,0x9fc06d6c \
  -postScript DumpAt.java 0x9fc05f90,0x9fc06d6c "$WORK/decomp.c" \
  2>&1 | tee "$WORK/ghidra.log"
STATUS=${PIPESTATUS[0]}
set -e
[ "$STATUS" -eq 0 ] || exit "$STATUS"

grep -q 'DumpAt: 9fc05f90' "$WORK/ghidra.log"
grep -q 'DumpAt: 9fc06d6c' "$WORK/ghidra.log"
grep -q 'FUN_9fc05f90' "$WORK/decomp.c"
grep -q 'FUN_9fc06d6c' "$WORK/decomp.c"
echo 'BOOT ROM PROBE PASS alternate=0x9fc05f90 epc=0x9fc06d6c'
