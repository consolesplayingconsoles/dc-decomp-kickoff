#!/usr/bin/env python3
"""Build a playable disc image: a copy of the original GDI with some files replaced. Stdlib only.

    disc_patch.py <original.gdi> <out dir> <path on disc>=<local file> [...]

Files are written in place, sector by sector, with each sector's error correction (EDC, P/Q
parity) recomputed: emulators ignore stale ECC, real hardware and GDEMU may not. No file moves, so
nothing that locates files by disc position breaks. A replacement must not be bigger than the
original (a smaller one is padded with zeros); growing a file needs a full disc rebuild.
"""
import os
import shutil
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gdi_read  # noqa: E402

# EDC (CRC-32, CD polynomial) and P/Q parity (Reed-Solomon over GF(256)), per ECMA-130.
_EDC_T = []
for _i in range(256):
    _e = _i
    for _ in range(8):
        _e = (_e >> 1) ^ (0xD8018001 if _e & 1 else 0)
    _EDC_T.append(_e)
_F, _B = [0] * 256, [0] * 256
for _i in range(256):
    _j = ((_i << 1) ^ (0x11D if _i & 0x80 else 0)) & 0xFF
    _F[_i] = _j
    _B[_i ^ _j] = _i


def _edc(data):
    c = 0
    for x in data:
        c = (c >> 8) ^ _EDC_T[(c ^ x) & 0xFF]
    return c


def _parity(buf, major_count, minor_count, major_mult, minor_inc, out):
    size = major_count * minor_count
    for major in range(major_count):
        idx = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            t = buf[idx]
            idx += minor_inc
            if idx >= size:
                idx -= size
            a ^= t
            b ^= t
            a = _F[a]
        a = _B[_F[a] ^ b]
        out[major] = a
        out[major + major_count] = a ^ b


def fix_sector(s):
    """Refresh EDC + P/Q of a 2352-byte Mode-1 sector after its user data changed."""
    s = bytearray(s)
    struct.pack_into("<I", s, 2064, _edc(bytes(s[0:2064])))
    s[2068:2076] = bytes(8)
    buf = bytes(s[12:2076])
    p = bytearray(172)
    _parity(buf, 86, 24, 2, 86, p)
    q = bytearray(104)
    _parity(buf + bytes(p), 52, 43, 86, 88, q)
    s[2076:2248] = p
    s[2248:2352] = q
    return bytes(s)


def main():
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    gdi, out = sys.argv[1], sys.argv[2]
    src = os.path.dirname(os.path.abspath(gdi))
    os.makedirs(out, exist_ok=True)
    lines = open(gdi).read().splitlines()
    for line in lines[1:]:
        p = line.split()
        if len(p) >= 6:
            name = " ".join(p[4:-1]).strip('"')
            print("  copying %s" % name)
            shutil.copyfile(os.path.join(src, name), os.path.join(out, name))
    out_gdi = os.path.join(out, os.path.basename(gdi))
    shutil.copyfile(gdi, out_gdi)
    disc = gdi_read.Disc(out_gdi)
    files = {path.upper(): (lba, size) for lba, size, path in disc.files()}
    for arg in sys.argv[3:]:
        path, local = arg.split("=", 1)
        key = "/" + path.strip("/").upper()
        if key not in files:
            raise SystemExit("[ERROR] %s is not on the disc" % path)
        lba, size = files[key]
        data = open(local, "rb").read()
        if len(data) > size:
            raise SystemExit("[ERROR] %s: %d bytes, the original is %d: it cannot grow in place"
                             % (path, len(data), size))
        data += bytes(size - len(data))
        for t in disc.tracks:
            if t["lba"] <= lba < t["lba"] + t["count"]:
                track = t
                break
        if track["sector"] != 2352:
            raise SystemExit("[ERROR] %s: track is not raw 2352-byte sectors" % path)
        with open(track["path"], "r+b") as f:
            for i in range(0, size, 2048):
                pos = (lba - track["lba"] + i // 2048) * 2352
                f.seek(pos)
                sec = bytearray(f.read(2352))
                chunk = data[i:i + 2048]
                sec[16:16 + len(chunk)] = chunk
                f.seek(pos)
                f.write(fix_sector(sec))
        disc = gdi_read.Disc(out_gdi)                    # re-open: verify from the image itself
        if disc.read(lba, size) != data:
            raise SystemExit("[ERROR] %s: read-back differs" % path)
        print("  replaced %s (%d bytes, %s), read back identical" % (path, len(data),
                                                                    "padded" if len(open(local, 'rb').read()) < size else "same size"))
    print("Disc image: %s" % out_gdi)


if __name__ == "__main__":
    main()
