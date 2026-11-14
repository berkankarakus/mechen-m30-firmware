#!/usr/bin/env bash
# Compare the stock and community automatic-index entry paths.
# Static Ghidra analysis only; no firmware image is modified or produced.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
STOCK=${1:-$ROOT/analysis/stock/fw}
COMMUNITY=${2:-$ROOT/analysis/community/fw}
GHIDRA=${GHIDRA:-/opt/homebrew/Cellar/ghidra/12.2/libexec/support/analyzeHeadless}
JAVA_HOME_OVERRIDE=${JAVA_HOME_OVERRIDE:-/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home}

[ -f "$STOCK/config.ap" ] || { echo "missing stock config.ap" >&2; exit 1; }
[ -f "$STOCK/udisk.ap" ] || { echo "missing stock udisk.ap" >&2; exit 1; }
[ -f "$COMMUNITY/config.ap" ] || { echo "missing community config.ap" >&2; exit 1; }
[ -f "$COMMUNITY/udisk.ap" ] || { echo "missing community udisk.ap" >&2; exit 1; }
[ -x "$GHIDRA" ] || { echo "missing Ghidra analyzeHeadless: $GHIDRA" >&2; exit 1; }

WORK=$(mktemp -d "${TMPDIR:-/private/tmp}/m30-ghidra-index-guards.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

decompile() {
  local label=$1
  local root=$2
  local app=$3
  local address=$4
  mkdir -p "$WORK/$label-project"
  set +e
  JAVA_HOME_OVERRIDE="$JAVA_HOME_OVERRIDE" \
  GHIDRA_JAVA_OPTIONS="${GHIDRA_JAVA_OPTIONS:--Duser.home=$WORK/home-$label}" \
    "$GHIDRA" "$WORK/$label-project" "m30$label" \
    -import "$root/$app.ap" \
    -loader BinaryLoader \
    -processor 'MIPS:LE:32:default' \
    -noanalysis \
    -scriptPath "$ROOT/tools/ghidra" \
    -postScript LoadAP.java "$root/$app.ap" \
    -postScript DumpAt.java "$address" "$WORK/$label.c" \
    2>&1 | tee "$WORK/$label.log"
  local rc=${PIPESTATUS[0]}
  set -e
  [ "$rc" -eq 0 ] || exit "$rc"
}

decompile stock-config "$STOCK" config 0x40094e0c
decompile community-config "$COMMUNITY" config 0x40094e0c
decompile stock-udisk "$STOCK" udisk 0x40055008
decompile community-udisk "$COMMUNITY" udisk 0x40055008

for label in stock-config community-config stock-udisk community-udisk; do
  grep -q 'DumpAt:' "$WORK/$label.log"
done

# The stock code branches on the incoming v0 status.  The community patch
# removes those conditionals, leaving the no-automatic-index path in place.
grep -Fq 'if (in_v0 == 0)' "$WORK/stock-config.c"
! grep -Fq 'in_v0' "$WORK/community-config.c"
grep -Fq 'if (in_v0 != 0)' "$WORK/stock-udisk.c"
! grep -Fq 'in_v0' "$WORK/community-udisk.c"

# Keep the byte-level guard in the same probe so a decompiler presentation
# change cannot make the evidence silently point at a different patch.
[ "$(od -An -tx1 -j 0x1e0d -N 1 "$COMMUNITY/config.ap" | tr -d ' \n')" = "10" ]
[ "$(od -An -tx1 -j 0x1909 -N 1 "$COMMUNITY/udisk.ap" | tr -d ' \n')" = "10" ]
[ "$(od -An -tx1 -j 0x1e0d -N 1 "$STOCK/config.ap" | tr -d ' \n')" = "22" ]
[ "$(od -An -tx1 -j 0x1909 -N 1 "$STOCK/udisk.ap" | tr -d ' \n')" = "22" ]

echo 'INDEX GUARD PROBE PASS config=in_v0-branch-removed udisk=dirty-branch-removed'
