#!/usr/bin/env bash
# ref_sigs.sh <SDK folder> <out dir> [<SDK 1.55J folder>]
# Function names from the reference decomp (Tokyo Bus Guide), as a signature table: <out>/tbg.sigs.
# No game disc needed: the decomp's matching build produces TBG's executable from its own sources
# plus an SDK, checked against TBG's SHA-1; its named functions are then hashed.
#   1. clone github.com/consolesplayingconsoles/tbg-decomp (a fork of lhsazevedo/tbg-decomp; ask the
#      user before cloning), or update an earlier clone;
#   2. build it in this skill's dc-tools image (wibo);
#   3. headless Ghidra hashes the named functions (ExportSigs.java).
# Docker by default; DC_LOCAL=1 (Linux x86_64: wibo on PATH, Ghidra from GHIDRA_INSTALL_DIR) runs it
# without containers, e.g. in a cloud workspace that cannot pull images.
# Two references:
#   - with a 1.55J folder (scripts/sdk_from_iso.py lays it out from the discs): the complete decomp,
#     the fork's latest main (every run pulls it; the build is checked against TBG's SHA-1 anyway),
#     built with SDK 1.55J (the libraries TBG shipped with); every function
#     the linker map names (1,462, about 1,260 hashable);
#   - without: tag kickoff-reference-1, built with <SDK folder> (R10.1); only the 176 library
#     functions its link script pins by address (162 hashable).
# Keep <out> local and under your home folder (Docker shares only that).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/docker_check.sh"
USAGE="usage: ref_sigs.sh <SDK folder> <out dir> [<SDK 1.55J folder>]"
SDK="$(cd "${1:?$USAGE}" && pwd)"
mkdir -p "${2:?$USAGE}"; OUT="$(cd "$2" && pwd)"
SDK155=""; [ -z "${3:-}" ] || SDK155="$(cd "$3" && pwd)"
REPO="${TBG_DECOMP_URL:-https://github.com/consolesplayingconsoles/tbg-decomp}"
if [ -n "$SDK155" ]; then
  for f in bin/elf2bin.exe shc/bin/asmsh.exe shinobi/lib/shinobi.lib; do
    [ -e "$SDK155/$f" ] || { echo "[ERROR] $SDK155 is not a 1.55J folder (no $f): lay it out with scripts/sdk_from_iso.py" >&2; exit 1; }
  done
  REF="${TBG_DECOMP_REF:-main}"
  MOUNTS=(-v "$SDK155":/sdk:ro)
else
  REF="${TBG_DECOMP_REF:-kickoff-reference-1}"
  dirof() { local f; f="$(find "$SDK" -iname "$1" -print -quit)"; [ -n "$f" ] || { echo "[ERROR] no $1 under $SDK" >&2; exit 1; }; dirname "$f"; }
  TOOLS="$(dirof asmsh.exe)"; SHCINC="$(dirof smachine.h)"; SHINC="$(dirof shinobi.h)"; LIB="$(dirof shinobi.lib)"
  MOUNTS=(-v "$TOOLS":/sdk/bin:ro -v "$TOOLS":/sdk/shc/bin:ro -v "$SHCINC":/sdk/shc/include:ro
          -v "$SHINC":/sdk/shinobi/include:ro -v "$LIB":/sdk/shinobi/lib:ro -v "$LIB":/sdk/shc/lib:ro)
fi

echo "1/3 reference decomp: $REPO at $REF"
[ -d "$OUT/tbg-decomp/.git" ] || git clone -q "$REPO" "$OUT/tbg-decomp"
git -C "$OUT/tbg-decomp" fetch -q --tags origin
git -C "$OUT/tbg-decomp" checkout -q --detach "origin/$REF" 2>/dev/null || git -C "$OUT/tbg-decomp" checkout -q "$REF"
echo "    at $(git -C "$OUT/tbg-decomp" log -1 --format='%h %s')"
rm -rf "$OUT/tbg-decomp/build/output_matching"; mkdir -p "$OUT/tbg-decomp/build/tmp"

echo "2/3 building Tokyo Bus Guide's executable from the decomp (a few minutes)"
if [ "${DC_LOCAL:-0}" = 1 ]; then         # wibo on PATH (Linux x86_64), SDK laid out as the decomp expects
  command -v wibo >/dev/null || { echo "[ERROR] DC_LOCAL=1 needs wibo on PATH" >&2; exit 1; }
  if [ -n "$SDK155" ]; then ROOT="$SDK155"
  else
    ROOT="$OUT/sdk-layout"; rm -rf "$ROOT"; mkdir -p "$ROOT/shc" "$ROOT/shinobi"
    ln -s "$TOOLS" "$ROOT/bin"; ln -s "$TOOLS" "$ROOT/shc/bin"; ln -s "$SHCINC" "$ROOT/shc/include"
    ln -s "$LIB" "$ROOT/shc/lib"; ln -s "$SHINC" "$ROOT/shinobi/include"; ln -s "$LIB" "$ROOT/shinobi/lib"
  fi
  win() { printf 'Z:%s' "$(printf %s "$1" | tr / '\\')"; }  # a path as wibo's Windows tools see it
  (cd "$OUT/tbg-decomp" && KATANA_SDK_DIR="$(win "$ROOT")" SHINOBI_DIR="$(win "$ROOT/shinobi")" \
    SHC_BIN="$(win "$ROOT/shc/bin")" SHC_LIB="$(win "$ROOT/shc/bin")" \
    SHC_INC="$(win "$ROOT/shc/include"),$(win "$ROOT/shinobi/include")" \
    SHC_TMP="$(win "$OUT/tbg-decomp/build/tmp")" make -f Makefile.matching) </dev/null > "$OUT/tbg-build.log" 2>&1 || true
else
  docker_ready "$HERE/tools-image"
  docker run --rm -v "$OUT/tbg-decomp":/app -w /app "${MOUNTS[@]}" \
    "${DC_TOOLS_IMAGE:-dc-tools}" make -f Makefile.matching </dev/null > "$OUT/tbg-build.log" 2>&1 || true
fi
grep -q "Build matches" "$OUT/tbg-build.log" || { tail -5 "$OUT/tbg-build.log"; echo "[ERROR] the reference build does not match: see $OUT/tbg-build.log" >&2; exit 1; }
cp "$OUT/tbg-decomp/build/output_matching/tbg.bin" "$OUT/tbg.bin"
if [ -n "$SDK155" ]; then                 # every function the linker map names
  tr -d '\r' < "$OUT/tbg-decomp/build/output_matching/tbg.map" \
    | awk '$NF=="ENT" && $2 ~ /^H.8C0[1-9A-F]/ { n=$1; sub(/^_/, "", n); print substr($2,3,8), n }' \
    | sort -u > "$OUT/tbg-names.txt"
else                                     # the library functions the link script pins
  grep '^define' "$OUT/tbg-decomp/build/lnk_matching_sdk.sub" \
    | sed -E 's/define _([^(]+)\(([0-9A-Fa-f]+)\).*/\2 \1/' > "$OUT/tbg-names.txt"
fi
echo "    matches TBG's SHA-1; $(wc -l < "$OUT/tbg-names.txt" | tr -d ' ') named functions"

echo "3/3 hashing them (Ghidra, a few minutes)"
"$HERE/ghidra/dghidra.sh" "$OUT" /work tbgproj -import /work/tbg.bin -overwrite \
  -loader BinaryLoader -loader-baseAddr 0x8C010000 -processor SuperH4:LE:32:default \
  -scriptPath /scripts -preScript DcPre.java -postScript ExportSigs.java /work/tbg-names.txt /work/tbg.sigs \
  > "$OUT/tbg-ghidra.log" 2>&1
grep -h "ExportSigs:" "$OUT/tbg-ghidra.log" | sed 's/.*ExportSigs: /    /' || true
[ -s "$OUT/tbg.sigs" ] || { echo "[ERROR] empty reference table: see $OUT/tbg-ghidra.log" >&2; exit 1; }
echo "-> $OUT/tbg.sigs ($(wc -l < "$OUT/tbg.sigs" | tr -d ' ') signatures)"
