#!/usr/bin/env bash
# Change one synthetic fixed-ROM return at a time and rerun the checked caller.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
if [ "$#" -gt 1 ]; then
  echo "usage: $0 [KER_INIT.BIN]" >&2
  exit 2
fi
INIT=${1:-$ROOT/analysis/community/fw/ker_init.bin}
LOG=$(mktemp "${TMPDIR:-/private/tmp}/m30-kernel-mmio-return-sweep.XXXXXX")
trap 'rm -f "$LOG"' EXIT

for call_index in 0 1 2 3 4 5 6; do
  mode="call${call_index}"
  if ! bash "$ROOT/tools/ghidra/run_kernel_init_mmio_probe.sh" \
      "$INIT" "$mode" >"$LOG" 2>&1; then
    cat "$LOG" >&2
    exit 1
  fi
  grep -F "KERNEL INIT MMIO P-CODE PASS entry=bfc32440" "$LOG" \
    | grep -F "return-mode=$mode"
done

echo "KERNEL INIT MMIO RETURN SWEEP PASS profiles=7 changed-return=0xdeadbeef other-returns=0"
