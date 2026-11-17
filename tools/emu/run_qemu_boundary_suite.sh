#!/usr/bin/env bash
# Run the read-only QEMU CPU/RAM boundary probes for the community corpus.
# These probes execute recovered MIPS code with explicit synthetic shims; they
# do not boot an ATJ2127 machine, modify firmware, or write an SD card.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
FW=${1:-$ROOT/analysis/community/fw}

[ -d "$FW" ] || { echo "missing firmware directory: $FW" >&2; exit 1; }

echo '[1/8] LCD resident boundary'
bash "$ROOT/tools/emu/run_qemu_lcd_probe.sh" "$FW/drv_lcd.drv"

echo '[2/8] DAC byte-transfer boundary'
bash "$ROOT/tools/emu/run_qemu_dac_probe.sh" "$FW/drv_dac.drv"

echo '[3/8] USB Audio packet/ring boundary'
bash "$ROOT/tools/emu/run_qemu_usb_audio_probe.sh"

echo '[4/8] usound leaf and producer boundaries'
bash "$ROOT/tools/emu/run_qemu_usound_leaf_probe.sh" "$FW/usound.drv"
bash "$ROOT/tools/emu/run_qemu_usound_producer_probe.sh" "$FW/usound.drv"

echo '[5/8] usound ring and port boundaries'
bash "$ROOT/tools/emu/run_qemu_usound_ring_probe.sh" "$FW/usound.drv"
bash "$ROOT/tools/emu/run_qemu_usound_port_probe.sh" "$FW/usound.drv"

echo '[6/8] usound producer-consumer chain'
bash "$ROOT/tools/emu/run_qemu_usound_chain_probe.sh" "$FW/usound.drv"

echo '[7/8] break-0 module-call envelope'
bash "$ROOT/tools/emu/run_qemu_usound_callback_probe.sh" "$FW/usound.drv"

echo '[8/8] independent TCG exception observation'
bash "$ROOT/tools/emu/run_qemu_exception_trace_probe.sh" "$FW/usound.drv"

echo 'QEMU BOUNDARY SUITE PASS'
