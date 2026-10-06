#!/usr/bin/env bash
# sdk_sigs.sh <SDK folder> <out dir>
# Build a signature table for every exported function in a Katana SDK's libraries:
# <out dir>/katana-sdk.sigs, for scripts/ghidra/ApplySigs.java. Any SDK layout: lbr.exe, lnk.exe
# and the *.lib files are found by name. Keep the output local: it is derived from the SDK.
#   1. lbr lists each library's modules; lnk links all of them into one ELF + a symbol map.
#   2. Headless Ghidra hashes every code symbol of the map (map_names.py: ENT, and the DAT symbols
#      inside code sections, i.e. the hand-written runtime routines; ExportSigs.java, folder mode).
# Containers by default (this skill's dc-tools image + scripts/ghidra/dghidra.sh); DC_LOCAL=1 runs
# wibo directly (Linux x86_64 only). Any failure stops with an error: never an empty table.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/docker_check.sh"
SDK="$(cd "${1:?usage: sdk_sigs.sh <SDK folder> <out dir>}" && pwd)"
mkdir -p "${2:?usage: sdk_sigs.sh <SDK folder> <out dir>}"; OUT="$(cd "$2" && pwd)"
LBR="$(find "$SDK" -iname lbr.exe -print -quit)"
[ -n "$LBR" ] || { echo "[ERROR] no lbr.exe under $SDK"; exit 1; }
TOOLS_REL="${LBR#"$SDK"/}"; TOOLS_REL="${TOOLS_REL%/*}"
rm -rf "$OUT/libs" "$OUT/link" "$OUT/elf" "$OUT/names" "$OUT/sigs"
mkdir -p "$OUT/libs" "$OUT/link" "$OUT/elf" "$OUT/names" "$OUT/sigs"

# Copy every Hitachi (SYSROF) library under a plain name (the tools choke on spaces), identical
# copies once. SDKs also ship ELF-format (*.elf.lib) and CodeWarrior libraries: skipped.
: > "$OUT/skipped.txt"
find "$SDK" -iname '*.lib' -print0 | while IFS= read -r -d '' f; do
  [ "$(head -c 1 "$f" | od -An -tx1 | tr -d ' ')" = "e0" ] || { echo "${f#"$SDK"/}" >> "$OUT/skipped.txt"; continue; }
  b="$(basename "$f" | tr 'A-Z' 'a-z' | tr -c 'a-z0-9.\n' '_')"; n="$b"; i=1
  while [ -e "$OUT/libs/$n" ]; do cmp -s "$f" "$OUT/libs/$n" && continue 2; n="${b%.lib}_$i.lib"; i=$((i+1)); done
  cp "$f" "$OUT/libs/$n"
done
echo "$(ls "$OUT/libs" | wc -l | tr -d ' ') Hitachi libraries ($(wc -l < "$OUT/skipped.txt" | tr -d ' ') other-format files skipped, see skipped.txt)"

STEPS='
  set -e
  tool() { find "$T" -maxdepth 1 -iname "$1.exe" -print -quit; }
  cd link
  for lib in ../libs/*.lib; do
    b="$(basename "$lib" .lib)"
    printf "library ..\\\\libs\\\\%s.lib\nlist\nexit\n" "$b" | wibo "$(tool lbr)" | tr -d "\r" > "$b.list" 2>&1 || true
    { printf "%s\n" elf "print $b.map" "output $b.elf"
      awk "/Entry date/ && \$1 != \"Entry\" { print \$1 }" "$b.list" | while read -r m; do printf "input ..\\\\libs\\\\%s.lib(%s)\n" "$b" "$m"; done
      printf "exit\n"; } > "$b.sub"
    wibo "$(tool lnk)" -subcommand="$b.sub" > "$b.log" 2>&1 || true
  done
'
echo "Linking every library into an ELF with a symbol map (a few minutes)"
if [ "${DC_LOCAL:-0}" = 1 ]; then
  command -v wibo >/dev/null || { echo "[ERROR] DC_LOCAL=1 needs wibo on PATH" >&2; exit 1; }
  (cd "$OUT" && T="$SDK/$TOOLS_REL" bash -c "$STEPS") </dev/null
else
  docker_ready "$HERE/tools-image"
  docker run --rm -v "$SDK":/sdk:ro -v "$OUT":/out -w /out -e T="/sdk/$TOOLS_REL" \
    "${DC_TOOLS_IMAGE:-dc-tools}" bash -c "$STEPS" </dev/null
fi

ok=0; bad=""
for m in "$OUT"/link/*.map; do
  b="$(basename "$m" .map)"
  if [ -f "$OUT/link/$b.elf" ] && tail -1 "$OUT/link/$b.log" | tr -d '\r' | grep -q COMPLETED; then
    cp "$OUT/link/$b.elf" "$OUT/elf/"
    python3 "$HERE/map_names.py" "$m" > "$OUT/names/$b.names"
    ok=$((ok+1))
  else
    bad="$bad $b"
  fi
done
echo "$ok libraries linked, $(cat "$OUT"/names/*.names 2>/dev/null | wc -l | tr -d ' ') exported functions${bad:+; failed:$bad}"
[ "$ok" -gt 0 ] || { echo "[ERROR] no library linked: see $OUT/link/*.log (is the tools image working?)" >&2; exit 1; }

# Hash with Ghidra. With little Docker memory, one library per run (resumable: done ones are kept).
if [ "${DC_LOCAL:-0}" != 1 ] && docker_low_memory; then
  n=0; total=$(ls "$OUT"/elf/*.elf | wc -l | tr -d ' ')
  for e in "$OUT"/elf/*.elf; do
    b="$(basename "$e" .elf)"; n=$((n+1))
    [ -s "$OUT/sigs/$b.sigs" ] && continue
    echo "  hashing $n/$total: $b"
    mkdir -p "$OUT/one/$b" && cp "$e" "$OUT/one/$b/"
    "$HERE/ghidra/dghidra.sh" "$OUT" /work "proj_$b" -import "/work/one/$b/$b.elf" -overwrite \
      -processor SuperH4:LE:32:default -scriptPath /scripts \
      -postScript ExportSigs.java /work/names /work/sigs >> "$OUT/ghidra.log" 2>&1
  done
else
  echo "Hashing every library with Ghidra (a few minutes)"
  "$HERE/ghidra/dghidra.sh" "$OUT" /work sdkproj -import /work/elf -overwrite \
    -processor SuperH4:LE:32:default -scriptPath /scripts \
    -postScript ExportSigs.java /work/names /work/sigs > "$OUT/ghidra.log" 2>&1
fi
missing=""; for e in "$OUT"/elf/*.elf; do b="$(basename "$e" .elf)"; [ -s "$OUT/sigs/$b.sigs" ] || [ ! -s "$OUT/names/$b.names" ] || missing="$missing $b"; done
[ -z "$missing" ] || { echo "[ERROR] no signatures for:$missing (see $OUT/ghidra.log; out of memory shows as 'Killed')" >&2; exit 1; }
cat "$OUT"/sigs/*.sigs > "$OUT/katana-sdk.sigs"
[ -s "$OUT/katana-sdk.sigs" ] || { echo "[ERROR] empty signature table" >&2; exit 1; }
echo "$(wc -l < "$OUT/katana-sdk.sigs" | tr -d ' ') signatures -> $OUT/katana-sdk.sigs"
