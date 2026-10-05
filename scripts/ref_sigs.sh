#!/usr/bin/env bash
# ref_sigs.sh <SDK folder> <out dir>
# Function names from the reference decomp (Tokyo Bus Guide), as a signature table: <out>/tbg.sigs.
# No game disc needed: the decomp's matching build produces TBG's executable from its own sources
# plus your SDK, checked against TBG's SHA-1; the functions its link script names are then hashed.
#   1. clone github.com/consolesplayingconsoles/tbg-decomp (a fork of lhsazevedo/tbg-decomp whose
#      matching build works with the Kochise R10.1 SDK; ask the user before cloning), pinned to the
#      tag kickoff-reference-1 (the commit proven here), so later changes to the fork cannot break it;
#   2. build it in this skill's dc-tools image (wibo), SDK folders found by name;
#   3. headless Ghidra hashes the named functions (ExportSigs.java).
# Keep <out> local and under your home folder (Docker shares only that).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/docker_check.sh"
SDK="$(cd "${1:?usage: ref_sigs.sh <SDK folder> <out dir>}" && pwd)"
mkdir -p "${2:?usage: ref_sigs.sh <SDK folder> <out dir>}"; OUT="$(cd "$2" && pwd)"
REPO="${TBG_DECOMP_URL:-https://github.com/consolesplayingconsoles/tbg-decomp}"
REF="${TBG_DECOMP_REF:-kickoff-reference-1}"
dirof() { local f; f="$(find "$SDK" -iname "$1" -print -quit)"; [ -n "$f" ] || { echo "[ERROR] no $1 under $SDK" >&2; exit 1; }; dirname "$f"; }
TOOLS="$(dirof asmsh.exe)"; SHCINC="$(dirof smachine.h)"; SHINC="$(dirof shinobi.h)"; LIB="$(dirof shinobi.lib)"

echo "1/3 reference decomp: $REPO at $REF"
[ -d "$OUT/tbg-decomp/.git" ] || git clone -q "$REPO" "$OUT/tbg-decomp"
git -C "$OUT/tbg-decomp" fetch -q --tags origin && git -C "$OUT/tbg-decomp" checkout -q "$REF"
mkdir -p "$OUT/tbg-decomp/build/tmp"
docker_ready "$HERE/tools-image"

echo "2/3 building Tokyo Bus Guide's executable from the decomp (a few minutes)"
docker run --rm -v "$OUT/tbg-decomp":/app -w /app \
  -v "$TOOLS":/sdk/bin:ro -v "$TOOLS":/sdk/shc/bin:ro -v "$SHCINC":/sdk/shc/include:ro \
  -v "$SHINC":/sdk/shinobi/include:ro -v "$LIB":/sdk/shinobi/lib:ro -v "$LIB":/sdk/shc/lib:ro \
  "${DC_TOOLS_IMAGE:-dc-tools}" make -f Makefile.matching </dev/null > "$OUT/tbg-build.log" 2>&1 || true
grep -q "Build matches" "$OUT/tbg-build.log" || { tail -5 "$OUT/tbg-build.log"; echo "[ERROR] the reference build does not match: see $OUT/tbg-build.log" >&2; exit 1; }
cp "$OUT/tbg-decomp/build/output_matching/tbg.bin" "$OUT/tbg.bin"
grep '^define' "$OUT/tbg-decomp/build/lnk_matching_sdk.sub" \
  | sed -E 's/define _([^(]+)\(([0-9A-Fa-f]+)\).*/\2 \1/' > "$OUT/tbg-names.txt"
echo "    matches TBG's SHA-1; $(wc -l < "$OUT/tbg-names.txt" | tr -d ' ') named library functions"

echo "3/3 hashing them (Ghidra, a few minutes)"
"$HERE/ghidra/dghidra.sh" "$OUT" /work tbgproj -import /work/tbg.bin -overwrite \
  -loader BinaryLoader -loader-baseAddr 0x8C010000 -processor SuperH4:LE:32:default \
  -scriptPath /scripts -preScript DcPre.java -postScript ExportSigs.java /work/tbg-names.txt /work/tbg.sigs \
  > "$OUT/tbg-ghidra.log" 2>&1
grep -h "ExportSigs:" "$OUT/tbg-ghidra.log" | sed 's/.*ExportSigs: /    /' || true
[ -s "$OUT/tbg.sigs" ] || { echo "[ERROR] empty reference table: see $OUT/tbg-ghidra.log" >&2; exit 1; }
echo "-> $OUT/tbg.sigs ($(wc -l < "$OUT/tbg.sigs" | tr -d ' ') signatures)"
