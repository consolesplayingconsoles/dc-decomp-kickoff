#!/usr/bin/env bash
# setup_tools.sh: install the tools DC_LOCAL=1 runs on, one step at a time, for a machine without Docker.
# Linux x86_64 only (wibo is a Linux program; Ghidra's decompiler is x86_64): on macOS or Windows use Docker.
#
#   bash scripts/setup_tools.sh --check     only report what is installed and what is missing
#   bash scripts/setup_tools.sh             install what is missing, then write <tools>/env.sh
#   source <tools>/env.sh                   in every shell that runs the skill's scripts
#
# <tools> is $DC_TOOLS_DIR (default ~/dc-tools). Each download is pinned and checked against its SHA-256:
# wibo and Ghidra read theirs from the Dockerfiles in this folder (scripts/tools-image, scripts/ghidra), so there
# is one place to update them; JDK 21 is pinned below. unshield comes from the system's package manager.
# Every step prints what it does; the first failure stops the run with the reason.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TOOLS="${DC_TOOLS_DIR:-$HOME/dc-tools}"
CHECK=0
[ "${1:-}" = "--check" ] && CHECK=1

JDK_URL="https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/OpenJDK21U-jdk_x64_linux_hotspot_21.0.12.1_1.tar.gz"
JDK_SHA256="ce79869e1307ed8ee1e2baa86a412b1eb5b75d10a01006d788a6f968bcfaee94"

arg() { sed -n "s/^ARG $2=//p" "$HERE/$1" | head -1; }       # an ARG default of a Dockerfile here
WIBO_URL="$(arg tools-image/Dockerfile WIBO_URL)";   WIBO_SHA256="$(arg tools-image/Dockerfile WIBO_SHA256)"
GHIDRA_URL="$(arg ghidra/Dockerfile GHIDRA_URL)";    GHIDRA_SHA256="$(arg ghidra/Dockerfile GHIDRA_SHA256)"
[ -n "$WIBO_URL$WIBO_SHA256$GHIDRA_URL$GHIDRA_SHA256" ] && [ -n "$WIBO_URL" ] && [ -n "$WIBO_SHA256" ] && [ -n "$GHIDRA_URL" ] && [ -n "$GHIDRA_SHA256" ] \
  || { echo "[ERROR] could not read the pinned URLs and checksums from the Dockerfiles in $HERE" >&2; exit 1; }

N=0; TOTAL=5; MISSING=0
step() { N=$((N + 1)); echo "[$N/$TOTAL] $*"; }
ok() { echo "      ok: $*"; }
need() { MISSING=$((MISSING + 1)); echo "      MISSING: $*"; }
die() { echo "[ERROR] $*" >&2; exit 1; }
warn() { echo "      note: $*"; }

sha_ok() {   # sha_ok <file> <sha256>
  local got; got="$(sha256sum "$1" | cut -d' ' -f1)"
  [ "$got" = "$2" ] || die "checksum mismatch for $1 (got $got, expected $2): the download is not the pinned file"
}
fetch() {    # fetch <url> <out> <sha256>
  echo "      downloading $(basename "$2") ..."
  curl -fsSL --retry 3 -o "$2" "$1" || die "download failed: $1"
  sha_ok "$2" "$3"
}
SUDO=""; [ "$(id -u)" != 0 ] && command -v sudo >/dev/null 2>&1 && SUDO="sudo -n"      # -n: never wait for a password
apt_install() {
  command -v apt-get >/dev/null 2>&1 || die "no apt-get here: install $* with this system's package manager, then run this again"
  [ "$(id -u)" = 0 ] || [ -n "$SUDO" ] || die "need root (or sudo) to install $*: run it as root, or install them yourself"
  $SUDO env DEBIAN_FRONTEND=noninteractive apt-get update -qq </dev/null >/dev/null \
    && $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold "$@" </dev/null >/dev/null \
    || die "could not install $* (no root, or sudo wants a password): install it yourself, then run this again"
}

# 1. the machine
step "machine: Linux x86_64, Python 3.6+, curl, unzip, tar"
[ "$(uname -s)" = Linux ] && [ "$(uname -m)" = x86_64 ] || die "this is $(uname -s) $(uname -m): DC_LOCAL needs Linux x86_64. Install Docker instead (the default route)."
py_ok() { command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 6) else 1)'; }
if py_ok; then ok "python3 $(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
elif [ "$CHECK" = 1 ]; then need "python3 3.6 or newer"
else
  echo "      installing python3"; apt_install python3
  py_ok || die "python3 3.6 or newer is still missing: install it with this system's package manager, then run this again"
  ok "python3 $(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
fi
# room for the tools (about 1 GB to download, about 2 GB unpacked) and memory for Ghidra
free_kb="$(df -Pk "${TOOLS%/*}" 2>/dev/null | awk 'NR==2 {print $4}')"
if [ -n "$free_kb" ] && [ "$free_kb" -lt 3145728 ]; then
  if [ "$CHECK" = 1 ]; then need "3 GB of free disk (only $((free_kb / 1024)) MB free)"; else die "only $((free_kb / 1024)) MB of disk is free here; the tools need about 3 GB"; fi
else ok "disk: $((${free_kb:-0} / 1024)) MB free"; fi
mem_kb="$(awk '/^MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null)"
if [ -n "$mem_kb" ] && [ "$mem_kb" -lt 3900000 ]; then warn "only $((mem_kb / 1024)) MB of RAM: Ghidra wants about 4 GB and may be killed on a small machine"; else ok "RAM: $((${mem_kb:-0} / 1024)) MB"; fi
miss=""
for c in curl unzip tar sha256sum; do command -v "$c" >/dev/null 2>&1 || miss="$miss $c"; done
if [ -n "$miss" ]; then
  if [ "$CHECK" = 1 ]; then need "$miss"; else echo "      installing:$miss"; apt_install curl unzip tar coreutils ca-certificates; ok "installed"; fi
else ok "curl unzip tar sha256sum"; fi

[ "$CHECK" = 1 ] || mkdir -p "$TOOLS/bin"

# 2. wibo (runs the Hitachi tools)
step "wibo (runs the Hitachi SDK tools)"
if [ -x "$TOOLS/bin/wibo" ]; then ok "$TOOLS/bin/wibo"
elif command -v wibo >/dev/null 2>&1; then ok "$(command -v wibo)"
elif [ "$CHECK" = 1 ]; then need "wibo"
else fetch "$WIBO_URL" "$TOOLS/bin/wibo" "$WIBO_SHA256"; chmod +x "$TOOLS/bin/wibo"; ok "$TOOLS/bin/wibo"; fi

# 3. unshield (unpacks the SDK's InstallShield discs)
step "unshield (optional: unpacks an SDK that comes as an InstallShield disc)"
if command -v unshield >/dev/null 2>&1; then ok "$(command -v unshield)"
elif [ "$CHECK" = 1 ]; then warn "unshield is not installed (only needed for an SDK disc image; an unpacked SDK does not need it)"
else
  if ( apt_install unshield ) >/dev/null 2>&1; then ok "$(command -v unshield)"
  else warn "unshield could not be installed (no root here). Only needed for an SDK disc image; an unpacked SDK does not need it. Carrying on."; fi
fi

# 4. JDK 21 (Ghidra 12 needs 21 or newer)
step "JDK 21 (for Ghidra)"
jdk_major() { "$1" -version 2>&1 | sed -n 's/.*version "\([0-9]*\).*/\1/p' | head -1; }
JAVA=""
if [ -x "$TOOLS/jdk/bin/java" ]; then JAVA="$TOOLS/jdk/bin/java"
elif command -v java >/dev/null 2>&1; then JAVA="$(command -v java)"; fi
if [ -n "$JAVA" ] && [ "$(jdk_major "$JAVA" || echo 0)" -ge 21 ] 2>/dev/null; then ok "$JAVA (Java $(jdk_major "$JAVA"))"
elif [ "$CHECK" = 1 ]; then need "JDK 21 or newer"
else
  fetch "$JDK_URL" "$TOOLS/jdk.tar.gz" "$JDK_SHA256"
  rm -rf "$TOOLS/jdk" && mkdir -p "$TOOLS/jdk" && tar -xzf "$TOOLS/jdk.tar.gz" -C "$TOOLS/jdk" --strip-components=1 && rm "$TOOLS/jdk.tar.gz"
  ok "$TOOLS/jdk (Java $(jdk_major "$TOOLS/jdk/bin/java"))"
fi

# 5. Ghidra
step "Ghidra"
GH=""
[ -x "${GHIDRA_INSTALL_DIR:-/nonexistent}/support/analyzeHeadless" ] && GH="$GHIDRA_INSTALL_DIR"
[ -z "$GH" ] && [ -x "$TOOLS/ghidra/support/analyzeHeadless" ] && GH="$TOOLS/ghidra"
if [ -n "$GH" ]; then ok "$GH"
elif [ "$CHECK" = 1 ]; then need "Ghidra"
else
  fetch "$GHIDRA_URL" "$TOOLS/ghidra.zip" "$GHIDRA_SHA256"
  echo "      unpacking (about 1 GB) ..."
  rm -rf "$TOOLS"/ghidra_* "$TOOLS/ghidra" && unzip -q "$TOOLS/ghidra.zip" -d "$TOOLS" && rm "$TOOLS/ghidra.zip"
  ln -s "$(ls -d "$TOOLS"/ghidra_* | head -1)" "$TOOLS/ghidra"
  GH="$TOOLS/ghidra"; ok "$GH"
fi

if [ "$CHECK" = 1 ]; then
  [ "$MISSING" = 0 ] && echo "Everything DC_LOCAL=1 needs is installed." || { echo "$MISSING missing: run this script without --check to install them."; exit 1; }
  exit 0
fi

# the environment the skill's scripts read
JAVA_HOME_LINE=""
[ -x "$TOOLS/jdk/bin/java" ] && JAVA_HOME_LINE="export JAVA_HOME=\"$TOOLS/jdk\"; export PATH=\"$TOOLS/jdk/bin:\$PATH\""
cat > "$TOOLS/env.sh" <<EOF
# source this before running the skill's scripts without Docker
export DC_LOCAL=1
export PATH="$TOOLS/bin:\$PATH"
export GHIDRA_INSTALL_DIR="$GH"
$JAVA_HOME_LINE
EOF
echo "Done. In every shell that runs the skill's scripts:  source $TOOLS/env.sh"
