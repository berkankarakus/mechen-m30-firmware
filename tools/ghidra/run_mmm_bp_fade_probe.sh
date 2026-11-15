#!/usr/bin/env bash
# Map mmm_bp.al and verify the fade/buffer diagnostic boundary.
# Static Ghidra analysis only; no decoder or DSP payload is executed.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
AL=${1:-$ROOT/analysis/community/fw/mmm_bp.al}
GHIDRA=${GHIDRA:-/opt/homebrew/Cellar/ghidra/12.2/libexec/support/analyzeHeadless}
JAVA_HOME_OVERRIDE=${JAVA_HOME_OVERRIDE:-/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home}

[ -f "$AL" ] || { echo "missing mmm_bp.al: $AL" >&2; exit 1; }
[ -x "$GHIDRA" ] || { echo "missing Ghidra analyzeHeadless: $GHIDRA" >&2; exit 1; }

WORK=$(mktemp -d "${TMPDIR:-/private/tmp}/m30-ghidra-mmm-bp.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/project"

set +e
JAVA_HOME_OVERRIDE="$JAVA_HOME_OVERRIDE" \
GHIDRA_JAVA_OPTIONS="${GHIDRA_JAVA_OPTIONS:--Duser.home=$WORK/home}" \
  "$GHIDRA" "$WORK/project" m30mmmbp \
  -import "$AL" \
  -loader BinaryLoader \
  -processor 'MIPS:LE:32:default' \
  -noanalysis \
  -scriptPath "$ROOT/tools/ghidra" \
  -postScript LoadAP.java "$AL" \
  -postScript DumpAt.java 0xbfc21590,0xbfc216a8,0x68021c8c,0xbfc27400,0xbfc274c8,0xbfc27520,0xbfc276ac,0x680a1ed4 "$WORK/decomp.c" \
  2>&1 | tee "$WORK/ghidra.log"
STATUS=${PIPESTATUS[0]}
set -e
[ "$STATUS" -eq 0 ] || exit "$STATUS"

grep -q 'LoadAP: blocks=5 ' "$WORK/ghidra.log"
grep -q 'DumpAt: bfc21590 -> FUN_bfc21590' "$WORK/ghidra.log"
grep -q 'DumpAt: bfc216a8 -> FUN_bfc216a8' "$WORK/ghidra.log"
grep -q 'DumpAt: 68021c8c -> FUN_68021c8c' "$WORK/ghidra.log"
grep -q 'DumpAt: bfc27400 -> FUN_bfc27400' "$WORK/ghidra.log"
grep -q 'DumpAt: bfc274c8 -> FUN_bfc274c8' "$WORK/ghidra.log"
grep -q 'DumpAt: bfc27520 -> FUN_bfc27520' "$WORK/ghidra.log"
grep -q 'DumpAt: bfc276ac -> FUN_bfc276ac' "$WORK/ghidra.log"
grep -q 'DumpAt: 680a1ed4 -> FUN_680a1ed4' "$WORK/ghidra.log"

# The first check is a real cross-reference to the diagnostic text.  The
# second and third checks identify the adjacent decoder state/buffer paths;
# neither is interpreted as proof of the exact audio attenuation algorithm.
grep -Fq '&UNK_bfc27470' "$WORK/decomp.c"
grep -Fq '&UNK_bfc21674' "$WORK/decomp.c"
grep -Fq '&UNK_bfc21684' "$WORK/decomp.c"
grep -Fq '&UNK_bfc21864' "$WORK/decomp.c"
grep -Fq '&UNK_bfc21880' "$WORK/decomp.c"
grep -q 'param_1 + 0xba' "$WORK/decomp.c"
grep -q 'param_1 + 0x8a' "$WORK/decomp.c"
grep -q 'param_1 + 0xc0' "$WORK/decomp.c"
grep -q 'param_1 + 0xcc' "$WORK/decomp.c"
grep -q 'param_1 + 0x81' "$WORK/decomp.c"
grep -q 'param_1\[2\] = 0x400' "$WORK/decomp.c"
grep -q 'param_3\[3\]' "$WORK/decomp.c"
grep -q 'param_1 + 0x70' "$WORK/decomp.c"
grep -q '0x200' "$WORK/decomp.c"

echo 'MMM BP FADE PASS diagnostic=fade-out/in buffer-state=verified attenuation=unresolved'
