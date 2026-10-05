#!/usr/bin/env bash
# Prepare the decomp from YOUR OWN disc: extract the executable, check it is the supported release,
# generate asm/ (one file per function) and text-map/. Nothing from the game is stored in git.
#   bash setup.sh <path to your .gdi> [quick|standard|deep]
set -euo pipefail
cd "$(dirname "$0")"
GDI="${1:?usage: bash setup.sh <your disc .gdi> [quick|standard|deep]}"
TIER="${2:-standard}"
PY="${PYTHON:-python3}"
BOOT="@BOOT@"                                    # boot file named in IP.BIN
SHA1="@SHA1@"                                    # of the supported release's boot file

"$PY" tools/gdi_read.py "$GDI" "$BOOT" 1ST_READ.BIN
got="$( (sha1sum 1ST_READ.BIN 2>/dev/null || shasum -a 1 1ST_READ.BIN) | cut -d' ' -f1)"
[ "$got" = "$SHA1" ] || { echo "[ERROR] $BOOT has SHA-1 $got, expected $SHA1: not the supported release (see README)"; exit 1; }
"$PY" tools/split_asm.py 1ST_READ.BIN "$(cat BASE)" functions.txt .
"$PY" tools/text_map.py 1ST_READ.BIN "$(cat BASE)" functions.txt text-map "$GDI" "$TIER"
chmod +x build.sh setup.sh 2>/dev/null || true
echo "Ready. Build with: SDK_PATH=<your Katana SDK folder> bash \"$PWD/build.sh\""
