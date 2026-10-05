#!/usr/bin/env bash
# sdk_sigs.sh <SDK folder> <out dir>
# Build a signature table for every exported function in a Katana SDK's libraries:
# <out dir>/katana-sdk.sigs, for scripts/ghidra/ApplySigs.java. Any SDK layout: lbr.exe, lnk.exe
# and the *.lib files are found by name. Keep the output local: it is derived from the SDK.
#   1. lbr lists each library's modules; lnk links all of them into one ELF + a symbol map.
#   2. Headless Ghidra hashes every ENT (code) symbol of the map (ExportSigs.java, folder mode).
# Containers by default (wibo image + scripts/ghidra/dghidra.sh); DC_LOCAL=1 runs wibo directly.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
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
if [ "${DC_LOCAL:-0}" = 1 ]; then
  (cd "$OUT" && T="$SDK/$TOOLS_REL" bash -c "$STEPS") </dev/null
else
  docker run --rm -v "$SDK":/sdk:ro -v "$OUT":/out -w /out -e T="/sdk/$TOOLS_REL" \
    "${DC_TOOLS_IMAGE:-lhsazevedo/tbg-decomp}" bash -c "$STEPS" </dev/null
fi

ok=0; bad=""
for m in "$OUT"/link/*.map; do
  b="$(basename "$m" .map)"
  if [ -f "$OUT/link/$b.elf" ] && tail -1 "$OUT/link/$b.log" | tr -d '\r' | grep -q COMPLETED; then
    cp "$OUT/link/$b.elf" "$OUT/elf/"
    tr -d '\r' < "$m" | awk '$NF=="ENT" && $2 ~ /^H'"'"'/ { n=$1; sub(/^_/, "", n); print substr($2,3,8), n }' > "$OUT/names/$b.names"
    ok=$((ok+1))
  else
    bad="$bad $b"
  fi
done
echo "$ok libraries linked, $(cat "$OUT"/names/*.names | wc -l | tr -d ' ') exported functions${bad:+; failed:$bad}"

"$HERE/ghidra/dghidra.sh" "$OUT" /work sdkproj -import /work/elf -overwrite \
  -processor SuperH4:LE:32:default -scriptPath /scripts \
  -postScript ExportSigs.java /work/names /work/sigs > "$OUT/ghidra.log" 2>&1
cat "$OUT"/sigs/*.sigs > "$OUT/katana-sdk.sigs"
echo "$(wc -l < "$OUT/katana-sdk.sigs" | tr -d ' ') signatures -> $OUT/katana-sdk.sigs"
