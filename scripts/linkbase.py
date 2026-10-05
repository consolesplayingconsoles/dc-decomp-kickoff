#!/usr/bin/env python3
"""Guess the address a Dreamcast executable was linked at, by counting self-pointers. Stdlib only.

    linkbase.py <1ST_READ.BIN>

Both bases load to the same RAM, but pointers inside the file use the one it was linked for:
most Katana builds use 0x8C010000 (P1), some (Crazy Taxi) 0x0C010000. Import at the wrong one and
Ghidra resolves almost no pointers: Crazy Taxi found 1,113 functions instead of the real set.
"""
import struct
import sys

BASES = (0x8C010000, 0x0C010000, 0xAC010000)


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    d = open(sys.argv[1], "rb").read()
    words = struct.unpack("<%dI" % (len(d) // 4), d[:len(d) // 4 * 4])
    counts = {b: sum(1 for w in words if b <= w < b + len(d)) for b in BASES}
    for b in BASES:
        print("0x%08X %7d pointers" % (b, counts[b]))
    print("link base: 0x%08X" % max(counts, key=counts.get))


if __name__ == "__main__":
    main()
