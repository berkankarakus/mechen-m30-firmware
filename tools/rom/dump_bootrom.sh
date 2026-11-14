#!/usr/bin/env bash
# Prepare or perform a read-only ATJ2127 Boot ROM dump.
#
# This wrapper deliberately exposes only simple_switch + read_mem2.  It never
# calls write_flash, read_lfi, or any other NAND-writing operation.  Without
# --execute it only prints the exact command that would be run.
set -euo pipefail

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

The player must already be in ADFU mode.  If it is still in normal mass
storage mode, switch it separately with actions_dump's explicit adfu_reboot
command, then rerun this script.
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

if [ -z "$actions_dump" ]; then
  if command -v actions_dump >/dev/null 2>&1; then
    actions_dump=$(command -v actions_dump)
  elif [ -x "/private/tmp/actions_dump" ]; then
    actions_dump=/private/tmp/actions_dump
  fi
fi

if [ -z "$adfus" ]; then
  for candidate in \
    "$(dirname "$0")/../../../actions_flash/payload/adfus.bin" \
    "/Users/berkankarakus/Projects/actions_flash/payload/adfus.bin" \
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
mkdir -p "$(dirname "$out")"

cmd=("$actions_dump" --id "$usb_id" --wait "$wait_seconds" chip 2127 blk_size 0x4000
  simple_switch 0xbfc18000 "$adfus"
  read_mem2 0x9fc00000 0x40000 "$out")

printf '%s\n' "ATJ2127 read-only Boot ROM dump"
printf '%s\n' "  source: $adfus"
printf '%s\n' "  range:  0x9fc00000..0x9fc3ffff (256 KiB)"
printf '%s\n' "  output: $out"
printf '  command:'
printf ' %q' "${cmd[@]}"
printf '\n'

if [ "$execute" -ne 1 ]; then
  printf '%s\n' 'DRY RUN: no USB command was sent. Add --execute only after the device is in ADFU mode.'
  exit 0
fi

if [ "$ack_ram_only" -ne 1 ]; then
  echo "refusing to access USB without --acknowledge-ram-only" >&2
  echo "this wrapper only uploads to RAM and reads ROM; it never writes flash" >&2
  exit 2
fi

printf '%s\n' 'Preflight: querying ADFU identity (read-only; no payload loaded yet).'
"$actions_dump" --id "$usb_id" --wait "$wait_seconds" chip 2127 adfu_info

"${cmd[@]}"
python3 "$(dirname "$0")/inspect_bootrom.py" "$out"
