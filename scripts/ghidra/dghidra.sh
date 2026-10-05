#!/bin/sh
# dghidra.sh <work dir> <analyzeHeadless args...>
# Runs headless Ghidra from the dc-ghidra image (built on first use from this folder's Dockerfile).
# <work dir> is mounted at /work: put binaries there and use /work/... paths in the arguments.
# The scripts in this folder are at /scripts (pass -scriptPath /scripts).
# Without Docker: DC_LOCAL=1 (or no docker on PATH) uses $GHIDRA_INSTALL_DIR (Ghidra 12.x + JDK 21)
# and rewrites /work and /scripts to the real folders.
set -eu
HERE=$(CDPATH= cd "$(dirname "$0")" && pwd)
WORK=$(CDPATH= cd "${1:?usage: dghidra.sh <work dir> <analyzeHeadless args...>}" && pwd); shift
if [ "${DC_LOCAL:-0}" = 1 ] || ! command -v docker >/dev/null 2>&1; then
  : "${GHIDRA_INSTALL_DIR:?no Docker: set GHIDRA_INSTALL_DIR to a Ghidra 12.x install (with a JDK 21)}"
  for a in "$@"; do
    case "$a" in
      /work|/work/*) a="$WORK${a#/work}" ;;
      /scripts|/scripts/*) a="$HERE${a#/scripts}" ;;
    esac
    set -- "$@" "$a"; shift
  done
  exec "$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$@" </dev/null
fi
IMAGE=${DC_GHIDRA_IMAGE:-dc-ghidra}
docker image inspect "$IMAGE" >/dev/null 2>&1 || docker build --platform linux/amd64 -t "$IMAGE" "$HERE" </dev/null
exec docker run --rm --platform linux/amd64 -v "$WORK":/work -v "$HERE":/scripts:ro "$IMAGE" "$@" </dev/null
