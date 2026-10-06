#!/usr/bin/env bash
# sdk_unpack.sh <SDK image .iso | .zip | folder> <out folder>
# Lay out any Katana SDK release as plain files, so sdk_scan.py and sdk_sigs.sh can read it.
#   1. a disc image or zip is copied out (iso_extract.py, no mounting); a folder is used as is;
#   2. every InstallShield set in it (data1.hdr, or data1.cab alone) is unpacked with unshield
#      (this folder's unshield-image, built on first use; DC_LOCAL=1: unshield on PATH) into
#      <out>/unpacked/<set>/.
# Discs older than InstallShield 5 (.z archives, no data1.hdr) are left as copied: say so.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
. "$HERE/docker_check.sh"
SRC="${1:?usage: sdk_unpack.sh <SDK image | zip | folder> <out folder>}"
mkdir -p "${2:?usage: sdk_unpack.sh <SDK image | zip | folder> <out folder>}"; OUT="$(cd "$2" && pwd)"
if [ -d "$SRC" ]; then FILES="$(cd "$SRC" && pwd)"
else python3 "$HERE/iso_extract.py" "$SRC" "$OUT/files"; FILES="$OUT/files"; fi
sets="$(cd "$FILES" && find . -iname 'data1.hdr' | sort)"
[ -n "$sets" ] || sets="$(cd "$FILES" && find . -iname 'data1.cab' | sort)"
if [ -z "$sets" ]; then
  echo "no InstallShield cabinets: nothing to unpack ($(find "$FILES" -iname '*.lib' | wc -l | tr -d ' ') .lib files as copied)"
  exit 0
fi
if [ "${DC_LOCAL:-0}" = 1 ]; then
  command -v unshield >/dev/null || { echo "[ERROR] DC_LOCAL=1 needs unshield on PATH (Debian/Ubuntu: apt-get install unshield)" >&2; exit 1; }
  unpack() { unshield -d "$OUT/unpacked/$1" x "$FILES/${2#./}"; }
else
  DC_IMAGE_TAG=dc-unshield docker_ready "$HERE/unshield-image"
  unpack() { docker run --rm "${MNT[@]}" dc-unshield unshield -d "/out/unpacked/$1" x "$ROOT/${2#./}"; }
fi
case "$FILES" in "$OUT"/*) MNT=(-v "$OUT":/out) ; ROOT=/out/${FILES#"$OUT"/} ;;
                 *) MNT=(-v "$FILES":/in:ro -v "$OUT":/out) ; ROOT=/in ;; esac
failed=""
while read -r s; do
  d="$(dirname "$s")"; name="$(echo "${d#./}" | tr '/ ' '__')"; [ "$d" != . ] || name=root
  echo "unpacking $s"
  unpack "$name" "$s" </dev/null > "$OUT/unshield-$name.log" 2>&1 || failed="$failed $s"
done <<< "$sets"
libs=$(find "$OUT/unpacked" -iname '*.lib' 2>/dev/null | wc -l | tr -d ' ')
[ -z "$failed" ] || echo "[note] unshield could not unpack:$failed (see $OUT/unshield-*.log)"
[ "$libs" -gt 0 ] || { echo "[ERROR] no .lib files unpacked" >&2; exit 1; }
echo "$libs .lib files unpacked -> $OUT/unpacked"
