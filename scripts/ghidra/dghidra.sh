#!/bin/sh
# dghidra.sh <work dir> <analyzeHeadless args...>
# Runs headless Ghidra from the dc-ghidra image (built on first use from this folder's Dockerfile).
# <work dir> is mounted at /work: put binaries there and use /work/... paths in the arguments.
# The scripts in this folder are at /scripts (pass -scriptPath /scripts).
# DC_GHIDRA_PROJECTS=<folder> (optional): keep the Ghidra projects there instead of in <work dir>
# (the first analyzeHeadless argument, /work, then means that folder), e.g. somewhere a clean of the
# work folder never wipes. Docker is the default and works on any OS. DC_LOCAL=1 (opt-in, Linux x86_64 only) uses
# $GHIDRA_INSTALL_DIR (Ghidra 12.x + JDK 21) and rewrites /work and /scripts to the real folders.
set -eu
HERE=$(CDPATH= cd "$(dirname "$0")" && pwd)
WORK=$(CDPATH= cd "${1:?usage: dghidra.sh <work dir> <analyzeHeadless args...>}" && pwd); shift
PROJ=$WORK
if [ -n "${DC_GHIDRA_PROJECTS:-}" ]; then
  mkdir -p "$DC_GHIDRA_PROJECTS"; PROJ=$(CDPATH= cd "$DC_GHIDRA_PROJECTS" && pwd)
  [ "${1:-}" = /work ] && { shift; set -- /projects "$@"; }
fi
if [ "${DC_LOCAL:-0}" = 1 ]; then
  : "${GHIDRA_INSTALL_DIR:?no Docker: set GHIDRA_INSTALL_DIR to a Ghidra 12.x install (with a JDK 21)}"
  for a in "$@"; do
    case "$a" in
      /projects) a="$PROJ" ;;
      /work|/work/*) a="$WORK${a#/work}" ;;
      /scripts|/scripts/*) a="$HERE${a#/scripts}" ;;
    esac
    set -- "$@" "$a"; shift
  done
  exec "$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$@" </dev/null
fi
command -v docker >/dev/null 2>&1 || { echo "[ERROR] Docker not found: install Docker (default, any OS), or on Linux x86_64 use DC_LOCAL=1 with GHIDRA_INSTALL_DIR" >&2; exit 1; }
IMAGE=${DC_GHIDRA_IMAGE:-dc-ghidra}
docker image inspect "$IMAGE" >/dev/null 2>&1 || docker build --platform linux/amd64 -t "$IMAGE" "$HERE" </dev/null
exec docker run --rm --platform linux/amd64 -v "$WORK":/work -v "$PROJ":/projects -v "$HERE":/scripts:ro "$IMAGE" "$@" </dev/null
