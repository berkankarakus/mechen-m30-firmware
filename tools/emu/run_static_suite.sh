#!/usr/bin/env bash
# Run the reproducible host and Ghidra checks for the M30 emulator boundary.
# All operations are read-only: no HEX or firmware image is produced.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
FW="$ROOT/analysis/community/fw"
AP="$ROOT/build/qemu-minimal-safe/work/verify/fw/music.ap"
HOST_ONLY=0

if [ "${1:-}" = "--host-only" ]; then
  HOST_ONLY=1
elif [ "$#" -gt 0 ]; then
  echo "usage: $0 [--host-only]" >&2
  exit 2
fi

echo "[1/3] host unit tests"
python3 -m unittest discover -s "$ROOT/tools/sim" -p 'test_*.py'
python3 -m unittest discover -s "$ROOT/tools/emu" -p 'test_*.py'
PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/provider_scan.py" \
  --all-files "$FW" >/dev/null

if [ "$HOST_ONLY" -eq 1 ]; then
  echo 'STATIC SUITE PASS host-only'
  exit 0
fi

[ -f "$FW/drv_ui.drv" ] || { echo "missing $FW/drv_ui.drv" >&2; exit 1; }
[ -f "$FW/kernel.drv" ] || { echo "missing $FW/kernel.drv" >&2; exit 1; }
[ -f "$FW/ker_xsys.bin" ] || { echo "missing $FW/ker_xsys.bin" >&2; exit 1; }
[ -f "$AP" ] || { echo "missing $AP" >&2; exit 1; }

echo "[2/3] Ghidra driver and kernel probes"
bash "$ROOT/tools/ghidra/run_drvui_pointer_probe.sh" "$FW/drv_ui.drv"
bash "$ROOT/tools/ghidra/run_drvui_pointer_cluster_probe.sh" "$FW/drv_ui.drv"
bash "$ROOT/tools/ghidra/run_drvui_b2_probe.sh" "$FW/drv_ui.drv"
bash "$ROOT/tools/ghidra/run_drvui_runtime_probe.sh" "$FW/drv_ui.drv"
bash "$ROOT/tools/ghidra/run_kernel_bank_boundary_probe.sh" "$FW/kernel.drv"
bash "$ROOT/tools/ghidra/run_kernel_loader_probe.sh" "$FW/kernel.drv"
bash "$ROOT/tools/ghidra/run_kernel_loader_refs_probe.sh" "$FW/kernel.drv"
bash "$ROOT/tools/ghidra/run_kernel_exception_probe.sh" "$FW/ker_xsys.bin"

echo "[3/3] real MIPS16 scroll probe"
bash "$ROOT/tools/ghidra/run_scroll_probe.sh" "$AP" next

echo 'STATIC SUITE PASS full'
