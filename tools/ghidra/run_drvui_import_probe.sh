#!/usr/bin/env bash
# Report MIPS16 indirect-call/import-selector pairs in the real M30 B3 bank.
# This is a read-only binutils cross-check for the Ghidra-mapped bank; it never
# executes or modifies firmware.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
DRIVER=${1:-$ROOT/analysis/community/fw/drv_ui.drv}

[ -f "$DRIVER" ] || { echo "missing driver: $DRIVER" >&2; exit 1; }

PYTHONPATH="$ROOT/tools/emu${PYTHONPATH:+:$PYTHONPATH}" \
  python3 "$ROOT/tools/emu/scan_mips16_imports.py" \
  "$DRIVER" \
  --require-selector 15 \
  --require-selector 17

echo 'DRV_UI IMPORT PASS selectors=15,17'
