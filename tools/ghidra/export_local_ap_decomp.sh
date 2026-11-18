#!/usr/bin/env bash
# Persist Ghidra C-like decompiles locally without adding vendor-derived output to Git.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
AP_DIR=${1:-$ROOT/analysis/community/fw}
OUT=${2:-$ROOT/analysis/local-evidence/decompiled/community}
GHIDRA=${GHIDRA:-/opt/homebrew/Cellar/ghidra/12.2/libexec/support/analyzeHeadless}

[ -d "$AP_DIR" ] || { echo "missing AP directory: $AP_DIR" >&2; exit 1; }
[ -x "$GHIDRA" ] || { echo "missing Ghidra analyzeHeadless: $GHIDRA" >&2; exit 1; }

if [ -z "${JAVA_HOME:-}" ] && [ -x /opt/homebrew/opt/openjdk@25/libexec/openjdk.jdk/Contents/Home/bin/java ]; then
  export JAVA_HOME=/opt/homebrew/opt/openjdk@25/libexec/openjdk.jdk/Contents/Home
fi

mkdir -p "$OUT"
WORK=$(mktemp -d "${TMPDIR:-/private/tmp}/m30-ap-decomp.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/home"
export JAVA_TOOL_OPTIONS="${JAVA_TOOL_OPTIONS:--Duser.home=$WORK/home}"

OLD_MANIFEST="$OUT/manifest.tsv"
NEXT_MANIFEST="$WORK/manifest.tsv"
printf 'module\tsha256\tfunctions\n' > "$NEXT_MANIFEST"
shopt -s nullglob
APS=("$AP_DIR"/*.ap)
[ ${#APS[@]} -gt 0 ] || { echo "no .ap files in $AP_DIR" >&2; exit 1; }

for AP in "${APS[@]}"; do
  NAME=$(basename "$AP" .ap)
  SHA=$(shasum -a 256 "$AP" | awk '{print $1}')
  OUTPUT="$OUT/$NAME.c"
  FUNCTIONS=
  if [ -f "$OUTPUT" ] && [ -f "$OLD_MANIFEST" ]; then
    FUNCTIONS=$(awk -F '\t' -v name="$NAME" -v sha="$SHA" '$1 == name && $2 == sha {print $3}' "$OLD_MANIFEST")
  fi

  if [ -n "$FUNCTIONS" ]; then
    printf '%s\t%s\t%s\n' "$NAME" "$SHA" "$FUNCTIONS" >> "$NEXT_MANIFEST"
    printf 'SKIP %s: hash unchanged (%s functions)\n' "$NAME" "$FUNCTIONS"
    continue
  fi

  PROJECT="$WORK/project-$NAME"
  LOG="$WORK/$NAME.log"
  mkdir -p "$PROJECT"
  if ! "$GHIDRA" "$PROJECT" "m30-$NAME" \
    -import "$AP" -loader BinaryLoader -processor 'MIPS:LE:32:default' -noanalysis \
    -scriptPath "$ROOT/tools/ghidra" \
    -postScript LoadAP.java "$AP" \
    -postScript DumpC.java "$OUTPUT" > "$LOG" 2>&1; then
    cat "$LOG" >&2
    exit 1
  fi
  FUNCTIONS=$(sed -n 's/.*DumpC: functions=\([0-9][0-9]*\).*/\1/p' "$LOG" | tail -1)
  [ -n "$FUNCTIONS" ] || { cat "$LOG" >&2; echo "missing DumpC function count for $NAME" >&2; exit 1; }
  printf '%s\t%s\t%s\n' "$NAME" "$SHA" "$FUNCTIONS" >> "$NEXT_MANIFEST"
  printf 'DONE %s: %s functions, sha256=%s\n' "$NAME" "$FUNCTIONS" "$SHA"
done

mv "$NEXT_MANIFEST" "$OLD_MANIFEST"
echo "LOCAL AP DECOMPILE ARCHIVE: $OUT"
