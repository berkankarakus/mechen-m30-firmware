#!/usr/bin/env bash
# Build the read-only-capable actions_flash host client on macOS.
# This compiles only; it does not open USB or talk to a player.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
SOURCE=${ACTIONS_FLASH_SOURCE:-$ROOT/../actions_flash/actions_dump.c}
OUTPUT=${1:-/private/tmp/actions_dump}

[ -f "$SOURCE" ] || {
  echo "missing actions_dump.c: $SOURCE" >&2
  echo "set ACTIONS_FLASH_SOURCE to the actions_flash checkout" >&2
  exit 1
}
command -v cc >/dev/null 2>&1 || { echo "cc not found" >&2; exit 1; }
command -v brew >/dev/null 2>&1 || { echo "Homebrew is required for libusb" >&2; exit 1; }

LIBUSB_PREFIX=${LIBUSB_PREFIX:-$(brew --prefix libusb)}
[ -f "$LIBUSB_PREFIX/include/libusb-1.0/libusb.h" ] || {
  echo "libusb headers not found under $LIBUSB_PREFIX" >&2
  exit 1
}
[ -f "$LIBUSB_PREFIX/lib/libusb-1.0.dylib" ] || {
  echo "libusb library not found under $LIBUSB_PREFIX" >&2
  exit 1
}

mkdir -p "$(dirname "$OUTPUT")"
cc -O2 -Wall -Wextra -std=c99 -pedantic -Wno-unused \
  -DUSE_LIBUSB=1 \
  -I"$LIBUSB_PREFIX/include" \
  -L"$LIBUSB_PREFIX/lib" \
  -o "$OUTPUT" "$SOURCE" -lusb-1.0

echo "built: $OUTPUT"
