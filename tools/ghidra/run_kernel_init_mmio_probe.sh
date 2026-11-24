#!/usr/bin/env bash
# Execute extracted FUN_bfc32440 with seeded MMIO and synthetic ROM returns.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
INIT=${1:-$ROOT/analysis/community/fw/ker_init.bin}
GHIDRA=${GHIDRA:-/opt/homebrew/Cellar/ghidra/12.2/libexec/support/analyzeHeadless}
EXPECTED_SHA256=f4c62848fb06ccbe6fba4323c4e29e46791c1abb25af648f0518eb0747492ec8

[ -f "$INIT" ] || { echo "missing ker_init.bin: $INIT" >&2; exit 1; }
[ -x "$GHIDRA" ] || { echo "missing Ghidra analyzeHeadless: $GHIDRA" >&2; exit 1; }
actual_sha=$(shasum -a 256 "$INIT" | awk '{print $1}')
[ "$actual_sha" = "$EXPECTED_SHA256" ] || {
  echo "ker_init.bin SHA-256 $actual_sha != $EXPECTED_SHA256" >&2
  exit 1
}
init_size=$(wc -c < "$INIT" | tr -d '[:space:]')
[ "$init_size" -ge $((0x828)) ] || { echo "ker_init.bin truncated before FUN_bfc32440" >&2; exit 1; }

WORK=$(mktemp -d "${TMPDIR:-/private/tmp}/m30-ghidra-kernel-mmio.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/home" "$WORK/project"

GHIDRA_JAVA_OPTIONS="${GHIDRA_JAVA_OPTIONS:--Duser.home=$WORK/home}" \
  "$GHIDRA" "$WORK/project" kernelmmio \
    -import "$INIT" \
    -loader BinaryLoader \
    -processor 'MIPS:LE:32:default' \
    -noanalysis \
    -scriptPath "$ROOT/tools/ghidra" \
    -postScript FlatLoad32.java "$INIT" 0xbfc32000 0 "$init_size" \
    -postScript RunKernelInitMmioProbe.java "$INIT" \
    >"$WORK/run.log" 2>&1 || {
      cat "$WORK/run.log" >&2
      exit 1
    }

grep -Fq 'KERNEL INIT MMIO P-CODE PASS entry=bfc32440' "$WORK/run.log" || {
  cat "$WORK/run.log" >&2
  exit 1
}
grep -F 'KERNEL INIT MMIO P-CODE PASS' "$WORK/run.log"
grep -F 'KERNEL INIT MMIO STATE' "$WORK/run.log"
