#!/usr/bin/env python3
"""Lay out the Katana SDK 1.55J from its two disc images, the way the reference decomp expects. Stdlib only.

    sdk_from_iso.py <out folder> <Vol.1 image> <Vol.2 image>

Images are ISOs (2048-byte sectors, as most copies are) of "Dreamcast SDK (Sega Library) Ver.1.55J"
Vol.1 (Common Disc) and Vol.2 (For SHC Users); Vol.3 (CodeWarrior) is not needed. Each is checked
against its Redump record (sector count, volume name, creation time) before anything is copied, in
either order. Result, under <out folder>:  bin/ (Vol.1 dc_sdk/bin)  shc/ and shinobi/ (Vol.2 dc_sdk).
No mounting and no platform tools: the discs' Joliet file system is read directly.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import iso_extract  # noqa: E402

# Redump: Dreamcast SDK (Sega Library) Ver.1.55J, discs 87866 (Vol.1) and 87867 (Vol.2).
DISCS = {
    "DCSDK_155J_1": dict(vol=1, sectors=251763, created="1999080317015300", redump=87866,
                         take=[("dc_sdk/bin", "bin")]),
    "DCSDK_155J_2": dict(vol=2, sectors=109185, created="1999080312383900", redump=87867,
                         take=[("dc_sdk/shc", "shc"), ("dc_sdk/shinobi", "shinobi")]),
}


class Iso(iso_extract.Iso):
    def __init__(self, path):
        super().__init__(path)
        self.size = os.path.getsize(path)
        self.created = self.sector(16)[813:829].decode("latin-1")
        if not self.joliet:
            raise SystemExit("[ERROR] %s: no Joliet file system" % path)


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    out = sys.argv[1]
    isos = [Iso(p) for p in sys.argv[2:]]
    seen = set()
    for iso, path in zip(isos, sys.argv[2:]):
        d = DISCS.get(iso.volume)
        if d is None:
            raise SystemExit("[ERROR] %s: volume %r is not SDK 1.55J Vol.1 or Vol.2" % (path, iso.volume))
        sectors = iso.size // 2048
        if iso.size % 2048 or sectors != d["sectors"] or iso.created != d["created"]:
            raise SystemExit("[ERROR] %s: does not match Redump disc %d (sectors %d, want %d; created %s, want %s)"
                             % (path, d["redump"], sectors, d["sectors"], iso.created, d["created"]))
        print("Vol.%d: %s matches Redump disc %d" % (d["vol"], os.path.basename(path), d["redump"]))
        seen.add(d["vol"])
    if seen != {1, 2}:
        raise SystemExit("[ERROR] need both Vol.1 and Vol.2")
    for iso in isos:
        for src, dst in DISCS[iso.volume]["take"]:
            n = iso.copy(iso.find(src), os.path.join(out, dst))
            print("  %s -> %s (%d files)" % (src, os.path.join(out, dst), n))
    for need in ("shc/bin/asmsh.exe", "shinobi/lib/shinobi.lib", "bin/elf2bin.exe"):
        if not os.path.exists(os.path.join(out, need)):
            raise SystemExit("[ERROR] %s missing after extraction" % need)
    print("SDK 1.55J -> %s" % os.path.abspath(out))


if __name__ == "__main__":
    main()
