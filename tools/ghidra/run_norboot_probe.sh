#!/usr/bin/env bash
# Map the extracted NORBREC member with its candidate mixed MIPS32/MIPS16 mode
# boundaries and verify the recovered MIPS16 calls to an unavailable ROM helper.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
NORBREC=${1:?usage: run_norboot_probe.sh NORBREC.BIN}
GHIDRA=${GHIDRA:-$(command -v analyzeHeadless || true)}
NORBREC_SHA256=8b11f25209e6a79474559b4b48d3a9d7f29d5f07633d234fe0eada9b8cd4e93d

[ -f "$NORBREC" ] || { echo "missing NORBREC: $NORBREC" >&2; exit 1; }
[ -n "$GHIDRA" ] && [ -x "$GHIDRA" ] || {
  echo "analyzeHeadless not found; install Ghidra or set GHIDRA to its executable path" >&2
  exit 1
}
actual_sha=$(shasum -a 256 "$NORBREC" | awk '{print $1}')
[ "$actual_sha" = "$NORBREC_SHA256" ] || {
  echo "NORBREC SHA-256 $actual_sha != $NORBREC_SHA256" >&2
  exit 1
}

WORK=$(mktemp -d "${TMPDIR:-/private/tmp}/m30-ghidra-norboot.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/home" "$WORK/project" "$WORK/javatmp"

GHIDRA_JAVA_OPTIONS="${GHIDRA_JAVA_OPTIONS:--Duser.home=$WORK/home -Djava.io.tmpdir=$WORK/javatmp}" \
  "$GHIDRA" "$WORK/project" m30norboot \
    -import "$NORBREC" \
    -loader BinaryLoader \
    -processor 'MIPS:LE:32:default' \
    -noanalysis \
    -scriptPath "$ROOT/tools/ghidra" \
    -postScript MapNorBoot.java "$NORBREC" 0xbfc31f00 \
    -postScript RunNorBootSetupProbe.java \
    -postScript RunNorBootReaderProbe.java \
    -postScript DumpC.java "$WORK/norboot.c" \
    >"$WORK/run.log" 2>&1 || {
      cat "$WORK/run.log" >&2
      exit 1
    }

grep -E 'NORBOOT (ROM EDGE|READER EDGE|SETUP P-CODE PASS|READER P-CODE PASS)' "$WORK/run.log"
grep -q 'NORBOOT READER P-CODE PASS' "$WORK/run.log" || {
  cat "$WORK/run.log" >&2
  exit 1
}
grep -q 'FUN_bfc3292c @ bfc3292c' "$WORK/norboot.c"
grep -q 'FUN_bfc32a48 @ bfc32a48' "$WORK/norboot.c"
grep -q 'func_0xbfc108d8(param_1,uVar1,param_3)' "$WORK/norboot.c"
grep -q 'func_0xbfc108d8(uVar5,puVar2,0x14)' "$WORK/norboot.c"
grep -q 'func_0xbfc108d8(_UNK_bfc32ab8,_UNK_bfc32abc,0x20)' "$WORK/norboot.c"
grep -q 'NORBOOT SETUP P-CODE PASS entry=0xbfc32a48' "$WORK/run.log"
grep -q 'NORBOOT READER P-CODE PASS entry=0xbfc3292c.*length=0x601 rounded-blocks=4' "$WORK/run.log"

echo "NORBOOT PROBE PASS mips32-entry=0xbfc32000 reader=0xbfc3292c setup=0xbfc32a48 dynamic-edges=5"
