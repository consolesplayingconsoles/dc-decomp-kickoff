#!/usr/bin/env python3
"""Copy every file out of a disc image or zip. Stdlib only.

    iso_extract.py <image .iso | .zip> <out folder>

ISO images (2048-byte sectors) are read directly, Joliet names when the disc has them, plain
ISO9660 otherwise (images that are also UDF carry an ISO9660 tree too). No mounting, any OS.
"""
import os
import struct
import sys
import zipfile


class Iso:
    def __init__(self, path):
        self.f = open(path, "rb")
        pvd = self.sector(16)
        if pvd[1:6] != b"CD001":
            raise SystemExit("[ERROR] %s: not an ISO image (2048-byte sectors expected)" % path)
        self.volume = pvd[40:72].decode("latin-1").strip()
        self.root, self.joliet = pvd[156:190], False
        for s in range(17, 32):
            d = self.sector(s)
            if d[1:6] != b"CD001" or d[0] == 255:
                break
            if d[0] == 2 and d[88:91] in (b"%/@", b"%/C", b"%/E"):
                self.root, self.joliet = d[156:190], True

    def sector(self, n, count=1):
        self.f.seek(n * 2048)
        return self.f.read(2048 * count)

    def entries(self, rec):
        lba, size = struct.unpack_from("<I", rec, 2)[0], struct.unpack_from("<I", rec, 10)[0]
        raw = self.sector(lba, (size + 2047) // 2048)[:size]
        o = 0
        while o < len(raw):
            n = raw[o]
            if n == 0:
                o = (o // 2048 + 1) * 2048
                continue
            r = raw[o:o + n]
            name = r[33:33 + r[32]]
            if name not in (b"\0", b"\1"):
                name = name.decode("utf-16-be" if self.joliet else "latin-1").split(";")[0]
                yield name.rstrip(".") or name, r
            o += n

    def find(self, path):
        rec = self.root
        for part in path.split("/"):
            for name, r in self.entries(rec):
                if name.lower() == part.lower():
                    rec = r
                    break
            else:
                raise SystemExit("[ERROR] %s not on %s" % (path, self.volume))
        return rec

    def copy(self, rec, dest):
        """Copy a directory record's tree to dest; returns the file count."""
        os.makedirs(dest, exist_ok=True)
        count = 0
        for name, r in self.entries(rec):
            out = os.path.join(dest, name)
            if r[25] & 2:
                count += self.copy(r, out)
                continue
            lba, size = struct.unpack_from("<I", r, 2)[0], struct.unpack_from("<I", r, 10)[0]
            with open(out, "wb") as w:
                left, n = size, lba
                while left > 0:
                    chunk = self.sector(n, min(512, (left + 2047) // 2048))[:left]
                    w.write(chunk)
                    left -= len(chunk)
                    n += 512
            count += 1
        return count


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    src, out = sys.argv[1], sys.argv[2]
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as z:
            z.extractall(out)
            n = sum(1 for i in z.infolist() if not i.is_dir())
    else:
        iso = Iso(src)
        n = iso.copy(iso.root, out)
    print("%d files -> %s" % (n, out))


if __name__ == "__main__":
    main()
