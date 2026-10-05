#!/bin/sh
# dghidra.sh <work dir> <analyzeHeadless args...>
# Runs headless Ghidra from the dc-ghidra image (built on first use from this folder's Dockerfile).
# <work dir> is mounted at /work: put binaries there and use /work/... paths in the arguments.
# The scripts in this folder are at /scripts (pass -scriptPath /scripts).
set -eu
HERE=$(CDPATH= cd "$(dirname "$0")" && pwd)
WORK=$(CDPATH= cd "${1:?usage: dghidra.sh <work dir> <analyzeHeadless args...>}" && pwd); shift
IMAGE=${DC_GHIDRA_IMAGE:-dc-ghidra}
docker image inspect "$IMAGE" >/dev/null 2>&1 || docker build --platform linux/amd64 -t "$IMAGE" "$HERE" </dev/null
exec docker run --rm --platform linux/amd64 -v "$WORK":/work -v "$HERE":/scripts:ro "$IMAGE" "$@" </dev/null
