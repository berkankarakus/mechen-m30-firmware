#!/usr/bin/env bash
# Execute the real directory-name callback with RAM-backed provider stubs.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
AP=${1:-$ROOT/analysis/community/fw/browser.ap}
GHIDRA=${GHIDRA:-/opt/homebrew/Cellar/ghidra/12.2/libexec/support/analyzeHeadless}
JAVA_HOME_OVERRIDE=${JAVA_HOME_OVERRIDE:-/opt/homebrew/opt/openjdk@25/libexec/openjdk.jdk/Contents/Home}
WORK=$(mktemp -d "${TMPDIR:-/private/tmp}/m30-ghidra-browser-directory.XXXXXX")
trap 'rm -rf "$WORK"' EXIT

[ -f "$AP" ] || { echo "missing browser AP: $AP" >&2; exit 1; }
[ -x "$GHIDRA" ] || { echo "missing Ghidra analyzeHeadless: $GHIDRA" >&2; exit 1; }
run_case() {
  local label=$1
  local current_index=$2
  local start_index=$3
  local row_count=$4
  local project="$WORK/$label/project"
  local home="$WORK/$label/home"
  local log="$WORK/$label.log"

  mkdir -p "$project" "$home"
  set +e
  JAVA_HOME="$JAVA_HOME_OVERRIDE" \
  JAVA_TOOL_OPTIONS="-Duser.home=$home" \
    "$GHIDRA" "$project" "m30browserdirectory-$label" \
    -import "$AP" \
    -loader BinaryLoader \
    -processor 'MIPS:LE:32:default' \
    -noanalysis \
    -scriptPath "$ROOT/tools/ghidra" \
    -postScript LoadAP.java "$AP" \
    -postScript RunBrowserDirectoryNameProbe.java \
      "$current_index" "$start_index" "$row_count" 2>&1 | tee "$log"
  local status=${PIPESTATUS[0]}
  set -e
  [ "$status" -eq 0 ] || exit "$status"
  grep -q 'BROWSER DIRECTORY NAME PASS' "$log"
}

run_case before 0 5 1
run_case inside 5 4 3
run_case after 8 5 1
echo 'BROWSER DIRECTORY NAME MATRIX PASS cases=before,inside,after'
