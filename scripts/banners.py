#!/usr/bin/env python3
"""Print the SDK/middleware version banners linked into a Dreamcast executable. Stdlib only.

    banners.py <1ST_READ.BIN>

Katana-era libraries embed "<module> Ver <x> Build:<date> <time>" strings. They name every
statically linked module and its exact build, before any disassembly: the fingerprint that says
which SDK libraries (and versions) to build function signatures from.
"""
import re
import sys

BANNER = re.compile(rb"[ -~]{0,60}?([A-Za-z][\w .@/-]{1,30}?)\s*Ver\.?\s*([\w.]+)\s*Build:\s*"
                    rb"([A-Z][a-z]{2} [ \d]\d \d{4}(?: [\d:]{8})?)")


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    data = open(sys.argv[1], "rb").read()
    seen = set()
    for m in BANNER.finditer(data):
        name = m.group(1).decode("ascii").strip(" -@")
        row = (name, m.group(2).decode("ascii"), m.group(3).decode("ascii"))
        if row not in seen:
            seen.add(row)
            print("%-20s %-12s %s   @0x%X" % (row + (m.start(1),)))
    old = re.compile(rb"([A-Za-z][\w.]{1,15})\s*Version\s*(\d[\w.]*)\s+((?:19|20)\d\d[/-]\d\d[/-]\d\d)")
    for m in old.finditer(data):                 # early (1998) form: "GDFS Version 0.49  1998-05-26"
        row = (m.group(1).decode("latin-1").strip(" -@"), m.group(2).decode("ascii"), m.group(3).decode("ascii"))
        if row not in seen:
            seen.add(row)
            print("%-20s %-12s %s   @0x%X" % (row + (m.start(1),)))
    if not seen:
        print("no banners: scrambled, compressed, or not a Katana build (check the first bytes decode as SH-4)")


if __name__ == "__main__":
    main()
