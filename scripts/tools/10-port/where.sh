#!/bin/sh
# where.sh ADDR...: the host addresses the native program's fault report prints, as functions and source lines
# (the program is build/native/<name>: the repo's folder without -decomp, as native_build.py's program_name names it)
root="$(cd "$(dirname "$0")/../.." && pwd)"
exe="$(basename "$root")"
exe="${exe%-decomp}"
exec addr2line -f -i -p -e "$root/build/native/$exe" "$@"
