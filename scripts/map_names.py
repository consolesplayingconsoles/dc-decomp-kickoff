#!/usr/bin/env python3
"""map_names.py <lnk .map>: the code symbols of a linked library, "<hex addr> <name>" per line. Stdlib only.

Functions written in C are ENT symbols. Hand-written assembly routines (the compiler runtime:
__modls, __bfslu, __quick_evn_mvn...) are DAT symbols, like data: those count as code when they
sit inside a P (code) section of the map. Names lose one leading underscore (C's), as in Ghidra.
"""
import re
import sys

text = open(sys.argv[1], encoding="latin-1").read().replace("\r", "")
code, section = [], None
for line in text.split("\n"):
    m = re.match(r"^(\S*)\s+H'([0-9A-Fa-f]{8})\s+-\s+H'([0-9A-Fa-f]{8})\s+H'", line)
    if not m:
        continue
    if m.group(1):
        section = m.group(1)          # a section's first range; the next ones leave the name out
    if section == "P":
        code.append((int(m.group(2), 16), int(m.group(3), 16)))
ent = set()
out = []
for m in re.finditer(r"^(\S+)\s+H'([0-9A-Fa-f]{8})\s+(ENT|DAT)\s*$", text, re.M):
    name, addr, kind = m.group(1), int(m.group(2), 16), m.group(3)
    if kind == "DAT" and (addr in ent or not any(a <= addr <= b for a, b in code)):
        continue
    if kind == "ENT":
        ent.add(addr)
    out.append("%08X %s" % (addr, name[1:] if name.startswith("_") else name))
print("\n".join(out))
