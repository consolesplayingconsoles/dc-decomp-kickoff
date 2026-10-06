#!/usr/bin/env python3
"""Which Katana SDK built this game? Match its library banners against SDK releases. Stdlib only.

    sdk_scan.py <SDK table .tsv | SDK folder> <1ST_READ.BIN>
    sdk_scan.py --tsv <SDK folder> > table.tsv

Library files carry the same "<module> Ver <x> Build:<date>" banners that banners.py reads from a
game. references/sdk-banners.tsv lists them for every publicly preserved release (names, versions
and dates only); pass it to name the SDK to ask the user for before they have any. Or pass a
folder holding as many SDKs as the user has, in any form: disc images (.iso), .zip files or
extracted folders, one SDK per top-level entry; every byte is read as it is (no extraction, so a
library packed in an installer or a .7z is not seen).

Prints the releases ranked by how many of the game's library builds (module, version, build date)
they contain, and the builds no release has. A full match is the SDK to use. Otherwise the game
was built with a release not in the list: suggest the one or two closest by date.
"""
import datetime
import mmap
import os
import re
import sys
import zipfile

BANNER = re.compile(rb"([A-Za-z][\w .@/-]{1,30}?)\s*Ver\.?\s*([\w.]+)\s*Build:\s*"
                    rb"([A-Z][a-z]{2} [ \d]\d \d{4}(?: [\d:]{8})?)")


def banners(data):
    return {(m.group(1).decode("ascii").strip(" -@"), m.group(2).decode("ascii"),
             " ".join(m.group(3).decode("ascii").split())) for m in BANNER.finditer(data)}


def date(b):
    return datetime.datetime.strptime(" ".join(b[2].split()[:3]), "%b %d %Y").date()


def scan_file(path):
    if zipfile.is_zipfile(path):
        out = set()
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if not info.is_dir():
                    out |= banners(z.read(info))
        return out
    if os.path.getsize(path) == 0:
        return set()
    with open(path, "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
        return banners(m)


def scan(entry):
    if os.path.isfile(entry):
        return scan_file(entry)
    out = set()
    for root, _, files in os.walk(entry, followlinks=True):
        for name in files:
            out |= scan_file(os.path.join(root, name))
    return out


def load(source):
    sdks = {}
    if os.path.isfile(source) and source.endswith(".tsv"):
        for line in open(source, encoding="utf-8"):
            if line.strip() and not line.startswith("#"):
                rel, mod, ver, built = line.rstrip("\n").split("\t")
                sdks.setdefault(rel, set()).add((mod, ver, built))
        return sdks
    for name in sorted(os.listdir(source)):
        if not name.startswith("."):
            print("scanning %s" % name, file=sys.stderr)
            found = scan(os.path.join(source, name))
            if found:
                sdks[name] = found
    return sdks


def main():
    a = sys.argv[1:]
    if len(a) == 2 and a[0] == "--tsv":
        sdks = load(a[1])
        print("# release\tmodule\tversion\tbuild date (library banners; names, versions, dates only)")
        for rel in sorted(sdks, key=lambda r: max(map(date, sdks[r]))):
            for b in sorted(sdks[rel]):
                print("%s\t%s\t%s\t%s" % ((rel,) + b))
        return
    if len(a) != 2:
        raise SystemExit(__doc__)
    sdks = load(a[0])
    if not sdks:
        raise SystemExit("[ERROR] no library banners in %s: no Katana SDK there" % a[0])
    game = banners(open(a[1], "rb").read())
    if not game:
        raise SystemExit("[ERROR] no banners in %s" % a[1])
    rank = sorted(sdks, key=lambda n: (-len(game & sdks[n]), n))
    best = len(game & sdks[rank[0]])
    print("The game links %d library builds. Releases by how many they contain:" % len(game))
    for name in rank:
        n = len(game & sdks[name])
        if n:
            print("  %3d/%d  %s (libraries up to %s)" % (n, len(game), name, max(map(date, sdks[name]))))
    if best == len(game):
        print("\nFull match: %s" % ", ".join(n for n in rank if len(game & sdks[n]) == best))
    else:
        newest = max(map(date, game))
        near = sorted(sdks, key=lambda n: abs((max(map(date, sdks[n])) - newest).days))[:2]
        print("\nNo release has them all (newest library build in the game: %s). Pick a close one: %s"
              % (newest, " or ".join(near)))
    print("\nPer library build (which releases have it):")
    for b in sorted(game):
        has = [n for n in rank if b in sdks[n]]
        print("  %-12s %-12s %-20s  %s" % (b + (", ".join(has) if has else "none",)))


if __name__ == "__main__":
    main()
