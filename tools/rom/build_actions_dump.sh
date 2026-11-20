#!/usr/bin/env bash
# Build the actions_flash host client used by the ROM readback wrapper.
# This compiles only; it does not open USB or talk to a player.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
actions_flash_root=${ACTIONS_FLASH_ROOT:-}
if [ -z "$actions_flash_root" ]; then
  common_git_dir=$(git -C "$ROOT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)
  main_checkout=""
  if [ -n "$common_git_dir" ]; then main_checkout=$(dirname "$common_git_dir"); fi
  for candidate in "$ROOT/../actions_flash" "$main_checkout/../actions_flash"; do
    if [ -d "$candidate" ]; then actions_flash_root=$candidate; break; fi
  done
fi
default_source=""
if [ -n "$actions_flash_root" ]; then
  default_source=$actions_flash_root/actions_dump.c
fi
SOURCE=${ACTIONS_FLASH_SOURCE:-$default_source}
OUTPUT=${1:-/private/tmp/actions_dump}

[ -f "$SOURCE" ] || {
  if [ -n "$SOURCE" ]; then echo "missing actions_dump.c: $SOURCE" >&2; fi
  echo "set ACTIONS_FLASH_ROOT or ACTIONS_FLASH_SOURCE to the actions_flash checkout" >&2
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
