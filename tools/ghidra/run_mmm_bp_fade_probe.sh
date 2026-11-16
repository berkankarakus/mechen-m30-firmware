#!/usr/bin/env bash
# Map mmm_bp.al and verify the fade/buffer diagnostic boundary.
# Static Ghidra analysis only; no decoder or DSP payload is executed.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
AL=${1:-$ROOT/analysis/community/fw/mmm_bp.al}
GHIDRA=${GHIDRA:-/opt/homebrew/Cellar/ghidra/12.2/libexec/support/analyzeHeadless}

if [ -z "${JAVA_HOME:-}" ] && command -v brew >/dev/null 2>&1; then
  JAVA_PREFIX=$(brew --prefix openjdk@25 2>/dev/null || true)
  JAVA_HOME="$JAVA_PREFIX/libexec/openjdk.jdk/Contents/Home"
fi

if [ -n "${JAVA_HOME:-}" ] && [ -x "$JAVA_HOME/bin/java" ]; then
  export JAVA_HOME
fi

[ -f "$AL" ] || { echo "missing mmm_bp.al: $AL" >&2; exit 1; }
[ -x "$GHIDRA" ] || { echo "missing Ghidra analyzeHeadless: $GHIDRA" >&2; exit 1; }

WORK=$(mktemp -d "${TMPDIR:-/private/tmp}/m30-ghidra-mmm-bp.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/project" "$WORK/home"

set +e
JAVA_TOOL_OPTIONS="-Duser.home=$WORK/home" \
  "$GHIDRA" "$WORK/project" m30mmmbp \
  -import "$AL" \
  -loader BinaryLoader \
  -processor 'MIPS:LE:32:default' \
  -noanalysis \
  -scriptPath "$ROOT/tools/ghidra" \
  -postScript LoadAP.java "$AL" \
  -postScript DumpAt.java 0xbfc21530,0xbfc21590,0xbfc216a8,0x68021c8c,0xbfc27400,0xbfc274c8,0xbfc27520,0xbfc276ac,0x680a1ed4 "$WORK/decomp.c" \
  -postScript DumpWords.java 0xbfc21694 0xbfc21698 \
  -postScript DumpWords.java 0xbfc21698 0xbfc2169c \
  -postScript DumpWords.java 0xbfc27488 0xbfc274cc \
  -postScript DumpWords.java 0xbfc2769c 0xbfc27734 \
  -postScript DumpInstructions.java 0xbfc21a3c 8 \
  -postScript DumpC.java "$WORK/all.c" \
  2>&1 | tee "$WORK/ghidra.log"
STATUS=${PIPESTATUS[0]}
set -e
[ "$STATUS" -eq 0 ] || exit "$STATUS"

grep -q 'LoadAP: blocks=5 ' "$WORK/ghidra.log"
grep -q 'DumpAt: bfc21530 -> FUN_bfc21530' "$WORK/ghidra.log"
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
grep -q 'param_1 + 0x81' "$WORK/decomp.c"
grep -q 'param_1 + 0xc0' "$WORK/decomp.c"
grep -q 'param_1 + 0xcc' "$WORK/decomp.c"
grep -q 'param_1 + 0x81' "$WORK/decomp.c"
grep -q 'param_1 + 0x88.*< 100' "$WORK/decomp.c"
grep -q 'uVar1 + uVar2 \* -0x3c' "$WORK/decomp.c"
grep -q '\* -1000' "$WORK/decomp.c"
grep -q '\* 1000' "$WORK/decomp.c"
grep -q 'param_1\[2\] = 0x400' "$WORK/decomp.c"
grep -q 'param_3\[3\]' "$WORK/decomp.c"
grep -q 'param_1 + 0x70' "$WORK/decomp.c"
grep -q '0x200' "$WORK/decomp.c"

# These literal-pool values are the actual callback/control boundaries used
# by the decompiled routines.  The odd MIPS16 values are recorded as values,
# not treated as new patch targets: the callback body is outside this module's
# safely recovered function set.
grep -q 'WORD address=bfc21698 value=0xbfc21a3d' "$WORK/ghidra.log"
grep -q 'WORD address=bfc21694 value=0x88888889' "$WORK/ghidra.log"
grep -q 'WORD address=bfc27488 value=0xbfc21a3d' "$WORK/ghidra.log"
grep -q 'WORD address=bfc274c4 value=0xbfc21a3d' "$WORK/ghidra.log"
grep -q 'WORD address=bfc2769c value=0x9fc21b00' "$WORK/ghidra.log"
grep -q 'WORD address=bfc276a0 value=0xbfc21a3d' "$WORK/ghidra.log"
grep -q 'WORD address=bfc2772c value=0xbfc274c9' "$WORK/ghidra.log"
grep -q 'WORD address=bfc27730 value=0xbfc2748d' "$WORK/ghidra.log"

# The unresolved callback target is recorded at instruction level.  A missing
#/bad decode here is evidence to keep it outside the patch model, not a reason
# to invent a function prototype.
grep -q 'INSN address=bfc21a3c' "$WORK/ghidra.log"
grep -q 'INSN address=bfc21a3e bytes=05 e8 break' "$WORK/ghidra.log"

# DumpC covers every recovered function in this image.  The fade-control byte
# is only read/cleared in the mapped set; no mapped function writes the value
# that arms the fade transition, so that setter remains outside this image's
# recovered call graph.
grep -q 'DumpC: functions=30' "$WORK/ghidra.log"
grep -q '^// ===== FUN_680a1ed4 ' "$WORK/all.c"
grep -q '^// ===== FUN_bfc21530 ' "$WORK/all.c"
[ "$(grep -c '+ 0x81' "$WORK/all.c")" -eq 4 ]
grep -Fq '((int)param_1 + 0x81) = 0' "$WORK/all.c"
grep -Fq 'param_1 + 0x81) = 0' "$WORK/all.c"

echo 'MMM BP FADE PASS diagnostic=fade-out/in buffer-state=verified attenuation=unresolved'
