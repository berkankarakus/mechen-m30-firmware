#!/usr/bin/env bash
# Build and, when available, run the isolated real-bank MIPS16 probe.
set -euo pipefail

[ $# -ge 1 ] || { echo "usage: $0 MUSIC.AP [OUTDIR]" >&2; exit 2; }
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
AP=$(realpath "$1")
OUT=${2:-/private/tmp/m30-qemu-probe}
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
PY=${PYTHON:-python3}
CROSS=${CROSS:-mipsel-linux-gnu-}
QEMU=${QEMU:-qemu-mipsel-static}

command -v "$PY" >/dev/null || { echo "missing Python: $PY" >&2; exit 1; }
for tool in "${CROSS}as" "${CROSS}ld"; do
  command -v "$tool" >/dev/null || { echo "missing MIPS binutils: $tool" >&2; exit 1; }
done

PYTHONPATH="$ROOT/tools/emu" "$PY" "$ROOT/tools/emu/make_qemu_probe.py" "$AP" "$OUT"
(
  cd "$OUT"
  "${CROSS}as" -EL -mabi=32 -mips32 -o qemu_probe.o qemu_probe.S
  "${CROSS}as" -EL -mabi=32 -mips32 -o qemu_probe_start.o qemu_probe_start.S
  "${CROSS}as" -EL -mabi=32 -mips16 -o banks.o banks.s
  "${CROSS}ld" -EL -m elf32ltsmip -T qemu_probe.ld -o qemu_probe.elf qemu_probe_start.o qemu_probe.o banks.o
)
echo "probe ELF: $OUT/qemu_probe.elf"
if command -v "$QEMU" >/dev/null; then
  STATUS="$OUT/qemu-status.bin"
  "$QEMU" -cpu 24Kc "$OUT/qemu_probe.elf" >"$STATUS"
  ACTUAL=$(
    "$PY" -c 'import struct, sys; data = open(sys.argv[1], "rb").read();
if len(data) != 4: raise SystemExit(f"expected 4 status bytes, got {len(data)}")
print("0x%04x" % struct.unpack("<I", data)[0])' "$STATUS"
  )
  if [ "$ACTUAL" != "0x8014" ]; then
    echo "QEMU scroll probe mismatch: expected 0x8014, got $ACTUAL" >&2
    exit 1
  fi
  echo "QEMU SCROLL PROBE PASS status=$ACTUAL"
else
  echo "QEMU user-mode not found: $QEMU; ELF was built but not executed" >&2
  exit 3
fi
