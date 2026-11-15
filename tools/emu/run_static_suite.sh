#!/usr/bin/env bash
# Run the reproducible host and Ghidra checks for the M30 emulator boundary.
# All operations are read-only: no HEX or firmware image is produced.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
FW="$ROOT/analysis/community/fw"
AP="$ROOT/build/qemu-minimal-safe/work/verify/fw/music.ap"
HOST_ONLY=0

# Keep all sequential Ghidra invocations inside one disposable cache/temp
# root.  Without these properties Ghidra falls back to /var/tmp, which is
# commonly read-only in the sandbox and produces noisy non-fatal cache errors.
GHIDRA_WORK=$(mktemp -d "${TMPDIR:-/private/tmp}/m30-ghidra-suite.XXXXXX")
trap 'rm -rf "$GHIDRA_WORK"' EXIT
mkdir -p "$GHIDRA_WORK/home" "$GHIDRA_WORK/cache" "$GHIDRA_WORK/tmp"
GHIDRA_JAVA_OPTIONS="${GHIDRA_JAVA_OPTIONS:--Duser.home=$GHIDRA_WORK/home}"
GHIDRA_JAVA_OPTIONS="$GHIDRA_JAVA_OPTIONS -Dapplication.cachedir=$GHIDRA_WORK/cache -Dapplication.tempdir=$GHIDRA_WORK/tmp"
export GHIDRA_JAVA_OPTIONS

if [ "${1:-}" = "--host-only" ]; then
  HOST_ONLY=1
elif [ "$#" -gt 0 ]; then
  echo "usage: $0 [--host-only]" >&2
  exit 2
fi

echo "[1/3] host unit tests"
python3 -m unittest discover -s "$ROOT/tools/sim" -p 'test_*.py'
python3 -m unittest discover -s "$ROOT/tools/emu" -p 'test_*.py'
python3 -m unittest discover -s "$ROOT/tools/rom" -p 'test_*.py'
PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/provider_scan.py" \
  --all-files "$FW" >/dev/null
PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/provider_scan.py" \
  --all-files "$FW" --exclude-name drv_ui.drv --require-zero >/dev/null
PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/provider_scan.py" \
  --all-files "$FW" --require-zero \
  --pointer 0xbfc0a408 --pointer 0xbfc0a578 --pointer 0xbfc0a6a0 \
  --pointer 0xbfc0a808 --pointer 0xbfc0a944 --pointer 0xbfc0ac98 \
  --pointer 0xbfc06d6c >/dev/null
PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/eq_menu_probe.py" \
  "$ROOT/analysis/community/fw/music.ap" \
  "$ROOT/analysis/community/fw/music.mcg" >/dev/null
PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/eq_binary_probe.py" \
  "$ROOT/analysis/community/fw/mengine.ap" \
  "$ROOT/analysis/community/fw/setting.ap" >/dev/null
PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/key_binary_probe.py" \
  "$ROOT/analysis/community/fw/key.drv" >/dev/null
PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/dac_binary_probe.py" \
  "$ROOT/analysis/community/fw/drv_dac.drv" >/dev/null
PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/lcd_binary_probe.py" \
  "$ROOT/analysis/community/fw/drv_lcd.drv" >/dev/null
PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/auddev_binary_probe.py" \
  "$ROOT/analysis/community/fw/aud_dev.drv" >/dev/null
PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/uhost_binary_probe.py" \
  "$ROOT/analysis/community/fw/uhost.drv" >/dev/null
PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/cards_binary_probe.py" \
  "$ROOT/analysis/community/fw/cards.drv" >/dev/null
PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/card_binary_probe.py" \
  "$ROOT/analysis/community/fw/card.drv" >/dev/null
PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/norud_binary_probe.py" \
  "$ROOT/analysis/community/fw/nor_ud.drv" >/dev/null
PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/filesystem_binary_probe.py" \
  "$ROOT/analysis/community/fw/exfatn.drv" \
  "$ROOT/analysis/community/fw/fat_32n.drv" >/dev/null
PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/dsp_binary_probe.py" \
  --analysis-root "$ROOT/analysis" >/dev/null
PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/mmm_bp_binary_probe.py" \
  --analysis-root "$ROOT/analysis" >/dev/null
PYTHONPATH="$ROOT/tools/emu" python3 "$ROOT/tools/emu/ui_resource_probe.py" \
  --analysis-root "$ROOT/analysis" >/dev/null

if [ "$HOST_ONLY" -eq 1 ]; then
  echo 'STATIC SUITE PASS host-only'
  exit 0
fi

[ -f "$FW/drv_ui.drv" ] || { echo "missing $FW/drv_ui.drv" >&2; exit 1; }
[ -f "$FW/kernel.drv" ] || { echo "missing $FW/kernel.drv" >&2; exit 1; }
[ -f "$FW/ker_xsys.bin" ] || { echo "missing $FW/ker_xsys.bin" >&2; exit 1; }
[ -f "$AP" ] || { echo "missing $AP" >&2; exit 1; }

echo "[2/3] Ghidra driver and kernel probes"
bash "$ROOT/tools/ghidra/run_asrc_probe.sh"
bash "$ROOT/tools/ghidra/run_music_v10111_delta_probe.sh"
bash "$ROOT/tools/ghidra/run_eq_probe.sh"
bash "$ROOT/tools/ghidra/run_eq_writer_probe.sh"
bash "$ROOT/tools/ghidra/run_eq_producer_probe.sh"
bash "$ROOT/tools/ghidra/run_eq_chain_probe.sh"
bash "$ROOT/tools/ghidra/run_index_guard_probe.sh" "$ROOT/analysis/stock/fw" "$ROOT/analysis/community/fw"
bash "$ROOT/tools/ghidra/run_drvui_pointer_probe.sh" "$FW/drv_ui.drv"
bash "$ROOT/tools/ghidra/run_drvui_pointer_cluster_probe.sh" "$FW/drv_ui.drv"
bash "$ROOT/tools/ghidra/run_drvui_b2_probe.sh" "$FW/drv_ui.drv"
bash "$ROOT/tools/ghidra/run_drvui_runtime_probe.sh" "$FW/drv_ui.drv"
bash "$ROOT/tools/ghidra/run_drvui_import_probe.sh" "$FW/drv_ui.drv"
bash "$ROOT/tools/ghidra/run_drvui_b3_table_probe.sh" "$FW/drv_ui.drv"
bash "$ROOT/tools/ghidra/run_drvui_b3_candidate_probe.sh" "$FW/drv_ui.drv"
bash "$ROOT/tools/ghidra/run_drvui_resident_probe.sh" "$FW/drv_ui.drv"
bash "$ROOT/tools/ghidra/run_browser_name_probe.sh" "$ROOT/analysis/community/fw/browser.ap"
bash "$ROOT/tools/ghidra/run_browser_layout_probe.sh" "$ROOT/analysis/community/fw/browser.ap"
bash "$ROOT/tools/ghidra/run_folder_nav_probe.sh"
bash "$ROOT/tools/ghidra/run_kernel_bank_boundary_probe.sh" "$FW/kernel.drv"
bash "$ROOT/tools/ghidra/run_kernel_loader_probe.sh" "$FW/kernel.drv"
bash "$ROOT/tools/ghidra/run_kernel_loader_refs_probe.sh" "$FW/kernel.drv"
bash "$ROOT/tools/ghidra/run_kernel_exception_probe.sh" "$FW/ker_xsys.bin"
bash "$ROOT/tools/ghidra/run_key_probe.sh" "$FW/key.drv"
bash "$ROOT/tools/ghidra/run_dac_probe.sh" "$FW/drv_dac.drv"
bash "$ROOT/tools/ghidra/run_lcd_probe.sh" "$FW/drv_lcd.drv"
bash "$ROOT/tools/ghidra/run_auddev_probe.sh" "$FW/aud_dev.drv"
bash "$ROOT/tools/ghidra/run_uhost_probe.sh" "$FW/uhost.drv"
bash "$ROOT/tools/ghidra/run_cards_probe.sh" "$FW/cards.drv"
bash "$ROOT/tools/ghidra/run_card_probe.sh" "$FW/card.drv"
bash "$ROOT/tools/ghidra/run_filesystem_probe.sh"
bash "$ROOT/tools/ghidra/run_mmm_dsp_loader_probe.sh" "$ROOT/analysis/community/fw/mmm_mp.al"
bash "$ROOT/tools/ghidra/run_decoder_callback_probe.sh"
bash "$ROOT/tools/ghidra/run_mmm_bp_fade_probe.sh" "$ROOT/analysis/community/fw/mmm_bp.al"

echo "[3/3] real MIPS16 scroll and folder-navigation probes"
for mode in next previous redraw; do
  bash "$ROOT/tools/ghidra/run_scroll_probe.sh" "$AP" "$mode"
done
for app in browser music; do
  for mode in next previous; do
    bash "$ROOT/tools/ghidra/run_folder_nav_pcode_probe.sh" "$app" "$mode"
  done
done

echo 'STATIC SUITE PASS full'
