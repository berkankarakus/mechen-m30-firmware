#!/usr/bin/env bash
# Prepare or perform an ATJ2127 Boot ROM readback.
#
# The wrapper's command vector does not call write_flash, read_lfi, or a
# NAND-writing operation. Execution uploads and runs the supplied code in
# device SRAM before reading ROM; payload safety is not established. Without
# --execute, it performs no USB or disk writes.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)

usage() {
  cat <<'EOF'
Usage: dump_bootrom.sh [options]

Options:
  --actions-dump PATH  actions_flash/actions_dump executable
  --adfus PATH         ATJ2127 payload/adfus.bin
  --out PATH            output file (default: rom-dump-9fc00000.bin)
  --id VID:PID         ADFU USB id (default: 10d6:10d6)
  --wait SECONDS       USB wait timeout (default: 30)
  --force               replace an existing output file
  --execute             perform the read; default is a dry run
  --acknowledge-ram-only
                        required with --execute; confirms no flash write
  -h, --help            show this help

The player must already enumerate as ADFU (10d6:10d6). Do not assume that
adfu_reboot switches this M30 from normal mass-storage mode: a public M30
analysis reports that its attempt left the player in FlashDisk mode. This
script does not issue adfu_reboot; only rerun after ADFU mode is independently
observed. See docs/related-projects.md for the scoped report.
EOF
}

actions_dump=""
adfus=""
out="rom-dump-9fc00000.bin"
usb_id="10d6:10d6"
wait_seconds=30
force=0
execute=0
ack_ram_only=0

while [ $# -gt 0 ]; do
  case "$1" in
    --actions-dump) [ $# -ge 2 ] || { echo "missing value for $1" >&2; exit 2; }; actions_dump=$2; shift 2 ;;
    --adfus) [ $# -ge 2 ] || { echo "missing value for $1" >&2; exit 2; }; adfus=$2; shift 2 ;;
    --out) [ $# -ge 2 ] || { echo "missing value for $1" >&2; exit 2; }; out=$2; shift 2 ;;
    --id) [ $# -ge 2 ] || { echo "missing value for $1" >&2; exit 2; }; usb_id=$2; shift 2 ;;
    --wait) [ $# -ge 2 ] || { echo "missing value for $1" >&2; exit 2; }; wait_seconds=$2; shift 2 ;;
    --force) force=1; shift ;;
    --execute) execute=1; shift ;;
    --acknowledge-ram-only) ack_ram_only=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$actions_dump" ] && [ -n "${ACTIONS_DUMP:-}" ]; then
  actions_dump=$ACTIONS_DUMP
fi

if [ -z "$actions_dump" ]; then
  if command -v actions_dump >/dev/null 2>&1; then
    actions_dump=$(command -v actions_dump)
  elif [ -x "/private/tmp/actions_dump" ]; then
    actions_dump=/private/tmp/actions_dump
  fi
fi

actions_flash_root=${ACTIONS_FLASH_ROOT:-}
if [ -z "$actions_flash_root" ]; then
  common_git_dir=$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)
  main_checkout=""
  if [ -n "$common_git_dir" ]; then main_checkout=$(dirname "$common_git_dir"); fi
  for candidate in "$ROOT/../actions_flash" "$main_checkout/../actions_flash"; do
    if [ -d "$candidate" ]; then actions_flash_root=$candidate; break; fi
  done
fi

if [ -z "$adfus" ] && [ -n "${ADFUS_BIN:-}" ]; then
  adfus=$ADFUS_BIN
fi
if [ -z "$adfus" ]; then
  for candidate in \
    "$actions_flash_root/payload/adfus.bin" \
    "payload/adfus.bin"; do
    if [ -f "$candidate" ]; then adfus=$candidate; break; fi
  done
fi

[ -n "$actions_dump" ] && [ -x "$actions_dump" ] || {
  echo "actions_dump executable not found; pass --actions-dump PATH" >&2; exit 1;
}
[ -f "$adfus" ] || {
  echo "ATJ2127 adfus.bin not found; pass --adfus PATH" >&2; exit 1;
}
[ "$(wc -c < "$adfus")" -gt 0 ] && [ "$(wc -c < "$adfus")" -le $((0x2000)) ] || {
  echo "adfus.bin must be between 1 byte and 0x2000 bytes" >&2; exit 1;
}
[ "$wait_seconds" -ge 1 ] 2>/dev/null || { echo "--wait must be positive" >&2; exit 2; }
[ "$out" != "/dev/null" ] || { echo "refusing to use /dev/null as dump target" >&2; exit 2; }
if [ -e "$out" ] && [ "$force" -ne 1 ]; then
  echo "output exists; choose another --out or pass --force: $out" >&2
  exit 1
fi
info_cmd=("$actions_dump" --id "$usb_id" --wait "$wait_seconds" chip 2127 adfu_info)
cmd=("$actions_dump" --id "$usb_id" --wait "$wait_seconds" chip 2127 blk_size 0x4000
  simple_switch 0xbfc18000 "$adfus"
  read_mem2 0x9fc00000 0x40000 "$out")

printf '%s\n' "ATJ2127 Boot ROM readback (executes supplied SRAM code; no flash-write command)"
printf '%s\n' "  source: $adfus"
printf '%s\n' "  range:  0x9fc00000..0x9fc3ffff (256 KiB)"
printf '%s\n' "  output: $out"
printf '  preflight:'
printf ' %q' "${info_cmd[@]}"
printf '\n'
printf '  command:'
printf ' %q' "${cmd[@]}"
printf '\n'

if [ "$execute" -ne 1 ]; then
  printf '%s\n' 'DRY RUN: no USB command was sent and no output path was created.'
  printf '%s\n' 'Execution first queries ADFU identity, then uploads/runs SRAM code and reads ROM.'
  exit 0
fi

if [ "$ack_ram_only" -ne 1 ]; then
  echo "refusing to access USB without --acknowledge-ram-only" >&2
  echo "the wrapper has no flash-write command, but the supplied SRAM payload is executed" >&2
  exit 2
fi

printf '%s\n' 'Preflight: querying ADFU identity (read-only; no payload loaded yet).'
INFO_LOG=$(mktemp "${TMPDIR:-/private/tmp}/m30-adfu-info.XXXXXX")
trap 'rm -f "$INFO_LOG"' EXIT
if ! "$actions_dump" --id "$usb_id" --wait "$wait_seconds" chip 2127 adfu_info >"$INFO_LOG" 2>&1; then
  cat "$INFO_LOG" >&2
  echo "ADFU identity query failed; refusing to upload the payload" >&2
  exit 1
fi
cat "$INFO_LOG"
if ! grep -Fq 'guess: chip = ATJ2127' "$INFO_LOG"; then
  echo "ADFU identity is not confirmed as ATJ2127; refusing to upload the payload" >&2
  echo "Expected the actions_dump line: guess: chip = ATJ2127" >&2
  exit 1
fi
printf '%s\n' 'ADFU identity PASS: ATJ2127'
printf '%s\n' 'This confirms only the chip-family guess; it does not prove M30-board or payload compatibility.'

mkdir -p "$(dirname "$out")"
"${cmd[@]}"
python3 "$(dirname "$0")/inspect_bootrom.py" "$out"
