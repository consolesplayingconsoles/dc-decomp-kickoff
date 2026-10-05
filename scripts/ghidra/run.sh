#!/bin/sh
# run.sh <1ST_READ.BIN> <project-dir> <report.txt> [base]   (base from linkbase.py, default 0x8C010000)
# Headless Ghidra import + full analysis of a raw Dreamcast executable, then the DcReport inventory.
# Needs GHIDRA_INSTALL_DIR and a JDK 21 (JAVA_HOME). Runs in the foreground: wait on this process,
# not on a pgrep of "analyzeHeadless" (that pattern matches the shell running the pgrep itself).
set -eu
BIN=${1:?usage: run.sh <1ST_READ.BIN> <project-dir> <report.txt>}
PROJ=${2:?project dir}
REPORT=${3:?report path}
BASE=${4:-0x8C010000}
HERE=$(CDPATH= cd "$(dirname "$0")" && pwd)
: "${GHIDRA_INSTALL_DIR:?set GHIDRA_INSTALL_DIR}" "${JAVA_HOME:?set JAVA_HOME to a JDK 21}"
mkdir -p "$PROJ"
exec "$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" dc -import "$BIN" -overwrite \
  -loader BinaryLoader -loader-baseAddr "$BASE" -processor SuperH4:LE:32:default \
  -scriptPath "$HERE" -preScript DcPre.java -postScript DcReport.java "$REPORT" \
  -analysisTimeoutPerFile 3600 </dev/null
