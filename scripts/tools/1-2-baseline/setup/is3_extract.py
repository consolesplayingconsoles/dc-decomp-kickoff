#!/usr/bin/env python3
"""Extract InstallShield 3 archives (.Z, or the ones embedded in a SETUP.EXE). Stdlib only.

    is3_extract.py <file> <out folder> [--list]

Early (1998-1999) Katana SDK installers are InstallShield 3: the files sit in one or more ".Z"
archives (magic 13 5D 65 8C), embedded whole in SETUP.EXE. Every archive in <file> is read:
directory table, file table (layout as ScummVM's InstallShieldV3 reader), then each file is
decompressed with PKWARE DCL "implode" (a port of zlib's contrib/blast/blast.c by Mark Adler) and
written under <out folder>/<archive offset>/<directory>/<name>. Directories here are the
installer's file groups (Group53...), not the install paths.
"""
import os
import re
import struct
import sys

MAXBITS, MAXWIN = 13, 4096
LITLEN = [11, 124, 8, 7, 28, 7, 188, 13, 76, 4, 10, 8, 12, 10, 12, 10, 8, 23, 8, 9, 7, 6, 7, 8, 7, 6,
          55, 8, 23, 24, 12, 11, 7, 9, 11, 12, 6, 7, 22, 5, 7, 24, 6, 11, 9, 6, 7, 22, 7, 11, 38, 7,
          9, 8, 25, 11, 8, 11, 9, 12, 8, 12, 5, 38, 5, 38, 5, 11, 7, 5, 6, 21, 6, 10, 53, 8, 7, 24,
          10, 27, 44, 253, 253, 253, 252, 252, 252, 13, 12, 45, 12, 45, 12, 61, 12, 45, 44, 173]
LENLEN = [2, 35, 36, 53, 38, 23]
DISTLEN = [2, 20, 53, 230, 247, 151, 248]
BASE = [3, 2, 4, 5, 6, 7, 8, 9, 10, 12, 16, 24, 40, 72, 136, 264]
EXTRA = [0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8]


def construct(rep):
    """Huffman table from blast's compact code-length list: (count per length, symbols)."""
    length = []
    for b in rep:
        length += [b & 15] * ((b >> 4) + 1)
    count = [0] * (MAXBITS + 1)
    for l in length:
        count[l] += 1
    offs = [0] * (MAXBITS + 2)
    for l in range(1, MAXBITS + 1):
        offs[l + 1] = offs[l] + count[l]
    symbol = [0] * len(length)
    for s, l in enumerate(length):
        if l:
            symbol[offs[l]] = s
            offs[l] += 1
    return count, symbol


LITCODE, LENCODE, DISTCODE = construct(LITLEN), construct(LENLEN), construct(DISTLEN)


class Blast:
    def __init__(self, data, pos):
        self.data, self.pos, self.bitbuf, self.bitcnt = data, pos, 0, 0

    def bits(self, need):
        val = self.bitbuf
        while self.bitcnt < need:
            val |= self.data[self.pos] << self.bitcnt
            self.pos += 1
            self.bitcnt += 8
        self.bitbuf = val >> need
        self.bitcnt -= need
        return val & ((1 << need) - 1)

    def decode(self, h):
        count, symbol = h
        bitbuf, left = self.bitbuf, self.bitcnt
        code = first = index = 0
        length = 1
        while True:
            while left:
                left -= 1
                code |= (bitbuf & 1) ^ 1
                bitbuf >>= 1
                c = count[length]
                if code < first + c:
                    self.bitbuf = bitbuf
                    self.bitcnt = (self.bitcnt - length) & 7
                    return symbol[index + (code - first)]
                index += c
                first = (first + c) << 1
                code <<= 1
                length += 1
            left = MAXBITS + 1 - length
            if left == 0:
                raise ValueError("bad code")
            bitbuf = self.data[self.pos]
            self.pos += 1
            if left > 8:
                left = 8

    def decompress(self, size):
        """PKWARE DCL implode: `size` bytes of output (the stream also ends with its own end code)."""
        lit = self.bits(8)
        dict_ = self.bits(8)
        if lit > 1 or not 4 <= dict_ <= 6:
            raise ValueError("not an implode stream")
        out = bytearray()
        while len(out) < size:
            if self.bits(1):
                sym = self.decode(LENCODE)
                length = BASE[sym] + self.bits(EXTRA[sym])
                if length == 519:
                    break
                sym = 2 if length == 2 else dict_
                dist = (self.decode(DISTCODE) << sym) + self.bits(sym) + 1
                if dist > len(out):
                    raise ValueError("distance too far back")
                for _ in range(length):          # byte by byte: the copy may overlap itself
                    out.append(out[-dist])
            else:
                out.append(self.decode(LITCODE) if lit else self.bits(8))
        return bytes(out[:size])


def archives(data):
    """Every IS3 archive in data: (offset, [(path, uncompressed, compressed, data offset)])."""
    for m in re.finditer(b"\x13\x5d\x65\x8c", data):
        base = m.start()
        try:
            u32 = lambda o: struct.unpack_from("<I", data, base + o)[0]
            u16 = lambda o: struct.unpack_from("<H", data, base + o)[0]
            dto, dcount = u32(41), u16(49)
            p, dirs = base + dto, []
            for _ in range(dcount):
                fc, cs, nl = struct.unpack_from("<HHH", data, p)
                dirs.append((data[p + 6:p + 6 + nl].decode("latin-1"), fc))
                p += cs
            files = []
            for name, fc in dirs:
                for _ in range(fc):
                    p += 3
                    usz, csz, off = struct.unpack_from("<III", data, p)
                    p += 26
                    nl = data[p]
                    fn = data[p + 1:p + 1 + nl].decode("latin-1")
                    p += 14 + nl
                    files.append(((name + "\\" + fn) if name else fn, usz, csz, off))
            yield base, files
        except (struct.error, IndexError, UnicodeDecodeError):
            continue


def main():
    if len(sys.argv) not in (3, 4):
        raise SystemExit(__doc__)
    data = open(sys.argv[1], "rb").read()
    out, listing = sys.argv[2], "--list" in sys.argv
    found = 0
    for base, files in archives(data):
        found += 1
        print("archive at 0x%X: %d files, %d MB" % (base, len(files), sum(f[1] for f in files) // 1048576))
        if listing:
            for path, usz, csz, off in files:
                print("  %9d %9d  %s" % (usz, csz, path))
            continue
        done = 0
        for path, usz, csz, off in files:
            dest = os.path.join(out, "0x%X" % base, *path.split("\\"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                blob = Blast(data, base + off).decompress(usz)
            except (ValueError, IndexError) as e:
                print("  [skip] %s: %s" % (path, e))
                continue
            with open(dest, "wb") as f:
                f.write(blob)
            done += 1
            if done % 250 == 0:
                print("  %d/%d files" % (done, len(files)))
        print("  %d files -> %s" % (done, os.path.join(out, "0x%X" % base)))
    if not found:
        raise SystemExit("[ERROR] no InstallShield 3 archive in %s" % sys.argv[1])


if __name__ == "__main__":
    main()
