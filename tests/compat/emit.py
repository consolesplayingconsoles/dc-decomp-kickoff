#!/usr/bin/env python3
"""Synthetic inputs for the map tool's readers, and what the readers find in them, as JSON. Stdlib only.

    emit.py                  the readers' output on every input, JSON on stdout
    emit.py --write <dir>    also writes each input as a file in <dir> (a viewer's readers can then be run on the same bytes)

The inputs are built here from nothing: no game data, so they can be committed and run anywhere. They exercise the
formats the readers know (Sega PRS compression, object trees stored as a memory image, Ninja chunk models and motions,
PowerVR/GIF/JPEG/PNG pictures). `check.py` compares this output with `golden.json`; a viewer compares its own readers'
output on the same files."""
import importlib.util
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "scripts")


def load_map_tool():
    sys.path.insert(0, SCRIPTS)
    spec = importlib.util.spec_from_file_location("model_map", os.path.join(SCRIPTS, "model_map.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Prs(object):
    """A PRS encoder for tests: literals, short and long copies, then the end marker; `plain` is what it decodes to."""

    def __init__(self):
        self.out, self.plain, self.n, self.ctrl = bytearray(), bytearray(), 0, 0

    def flag(self, bit):
        if self.n == 0:
            self.ctrl = len(self.out)
            self.out.append(0)
        if bit:
            self.out[self.ctrl] |= 1 << self.n
        self.n = (self.n + 1) % 8

    def literal(self, data):
        for b in bytearray(data):
            self.flag(1)
            self.out.append(b)
            self.plain.append(b)

    def copy(self, off, size):
        """Copy `size` bytes from `-off` bytes back (off positive)."""
        if size <= 5 and off <= 256:
            self.flag(0), self.flag(0), self.flag((size - 2) >> 1), self.flag((size - 2) & 1)
            self.out.append(256 - off)
        else:
            self.flag(0), self.flag(1)
            small = 2 < size < 10
            self.out += struct.pack("<H", ((0x2000 - off) << 3) | (size - 2 if small else 0))
            if not small:
                self.out.append(size - 1)
        for _ in range(size):
            self.plain.append(self.plain[-off])

    def end(self):
        self.flag(0), self.flag(1)
        self.out += b"\x00\x00"
        return bytes(self.out)


def prs_fixtures():
    lit = Prs()
    lit.literal(b"Dreamcast")
    a = lit.end()
    mix = Prs()
    mix.literal(b"ABCDEFGH")
    mix.copy(8, 3)           # short copy
    mix.literal(b"xyz")
    mix.copy(11, 7)          # long copy, size 3 to 9
    mix.copy(4, 20)          # long copy with a size byte
    mix.copy(1, 250)         # a run (the longest copy is 256)
    b = mix.end()
    return {"prs_literals.bin": (a, bytes(lit.plain)), "prs_copies.bin": (b, bytes(mix.plain))}


def tree_fixture():
    """Five objects in a chain (child, sibling, child, sibling) at a load address, one chunk model, one basic model."""
    base = 0x8C100000
    buf = bytearray(0x400)

    def obj(o, model, child, sibling):
        struct.pack_into("<II3f3i3fII", buf, o, 0, model, 1.0, 2.0, 3.0, 0, 0, 0, 1.0, 1.0, 1.0, child, sibling)
    chunk, basic = base + 0x120, base + 0x200
    obj(0x000, chunk, base + 0x034, 0)
    obj(0x034, 0, 0, base + 0x068)
    obj(0x068, basic, base + 0x09C, 0)
    obj(0x09C, 0, 0, base + 0x0D0)
    obj(0x0D0, chunk, 0, 0)
    struct.pack_into("<II3ff", buf, 0x120, base + 0x140, base + 0x180, 0.0, 0.0, 0.0, 2.5)   # chunk model
    buf[0x140:0x144] = bytes([32, 0, 2, 0])                                                   # vertex chunk: 2 words
    buf[0x14C] = 0xFF
    buf[0x180:0x184] = bytes([8, 0, 0, 0])                                                    # texture, then the end
    buf[0x184] = 0xFF
    struct.pack_into("<IIiIIHH4f", buf, 0x200, base + 0x240, 0, 3, base + 0x280, base + 0x2C0, 1, 1, 0.0, 0.0, 0.0, 4.0)   # basic model
    struct.pack_into("<9f", buf, 0x240, 0, 0, 0, 1, 0, 0, 0, 1, 0)
    struct.pack_into("<HHIIIII", buf, 0x280, 0, 1, base + 0x2A0, 0, 0, 0, 0)
    struct.pack_into("<3h", buf, 0x2A0, 0, 1, 2)
    struct.pack_into("<IIfI I", buf, 0x2C0, 0xFF80C040, 0, 1.0, 0, 0)
    return bytes(buf)


def ninja_fixture():
    """NJTL (two texture names) then NJCM (one object with a model), starting at offset 4."""
    names = b"TEXA\x00\x00\x00\x00TEXB\x00\x00\x00\x00"
    tl = struct.pack("<II", 8, 2) + struct.pack("<3I", 32, 0, 0) + struct.pack("<3I", 40, 0, 0)
    tl = tl.ljust(32, b"\x00") + names
    cm = bytearray(0x4C)
    struct.pack_into("<II3f3i3fII", cm, 0, 0, 0x34, 0.0, 0.0, 0.0, 0, 0, 0, 1.0, 1.0, 1.0, 0, 0)
    struct.pack_into("<II3ff", cm, 0x34, 0, 0, 0.0, 0.0, 0.0, 6.5)
    return b"\x00" * 4 + b"NJTL" + struct.pack("<I", len(tl)) + tl + b"NJCM" + struct.pack("<I", len(cm)) + bytes(cm)


def motion_fixture():
    """An NMDM motion: two objects, position and angle keys; the first object has a moving position."""
    data = bytearray(92)
    struct.pack_into("<IIHH", data, 0, 12, 10, 3, 2)
    struct.pack_into("<2I2I", data, 12, 44, 76, 2, 1)
    struct.pack_into("<I3f", data, 44, 0, 0.0, 0.0, 0.0)
    struct.pack_into("<I3f", data, 60, 10, 1.0, 2.0, 3.0)
    struct.pack_into("<I3i", data, 76, 0, 0, 0x4000, 0)
    return b"NMDM" + struct.pack("<I", len(data)) + bytes(data)


def picture_fixtures():
    def pvrt(w, h, dt, pf):
        body = w * h * 2
        return b"PVRT" + struct.pack("<I", body + 8) + bytes([pf, dt, 0, 0]) + struct.pack("<2H", w, h) + b"\x00" * body
    names = b"".join(struct.pack("<H", i) + (n + b"\x00" * 28)[:28] for i, n in enumerate([b"face_a", b"face_b"]))
    pvm = b"PVMH" + struct.pack("<I", 4 + len(names)) + struct.pack("<2H", 8, 2) + names
    pvm = pvm.ljust(0x80, b"\x00") + pvrt(8, 8, 1, 1) + pvrt(16, 8, 9, 2)
    gif = b"GIF89a" + struct.pack("<2H", 24, 16) + b"\x00" * 8
    png = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + struct.pack(">2I", 32, 20) + b"\x00" * 8
    jpg = b"\xff\xd8\xff\xe0\x00\x04\x00\x00\xff\xc0\x00\x0b\x08" + struct.pack(">2H", 12, 40) + b"\x01\x01\x11\x00"
    return {"pic_pvm.bin": pvm, "pic_gif.bin": gif, "pic_png.bin": png, "pic_jpg.bin": jpg}


def results(mm):
    out, files = {}, {}
    for name, (stream, plain) in prs_fixtures().items():
        files[name] = stream
        got = mm.prs_decompress(stream)
        assert got == plain, name + ": the PRS reader does not give back what the test encoder put in"
        out["prs:" + name] = {"bytes": len(got), "hex": got[:48].hex()}
    files["tree.bin"] = tree = tree_fixture()
    trees, base = mm.find_object_trees(tree)
    out["trees:tree.bin"] = {"base": base, "trees": [[o, n, round(r, 3)] for o, n, r in trees]}
    files["ninja.bin"] = nj = ninja_fixture()
    out["ninja:ninja.bin"] = [[o, nb, objs, round(r, 3), names] for o, nb, objs, r, names in mm.find_ninja(nj)]
    files["motion.njm"] = mo = motion_fixture()
    r = mm.njm_read(mo, 2)
    out["motion:motion.njm"] = [r[0], r[1], r[2], r[3]] if r else None
    mb = 1 << 20
    out["stretches"] = {str(n): mm.stretch_starts(n) for n in (0, mb, 16 * mb, 16 * mb + 1, 28 * mb, 28 * mb + 1, 100 * mb)}
    for name, data in picture_fixtures().items():
        files[name] = data
        out["pictures:" + name] = [[o, k, w, h, dt, pf, nb, nm] for o, k, w, h, dt, pf, nb, nm in mm.find_pictures(data)]
    return out, files


def main():
    mm = load_map_tool()
    out, files = results(mm)
    if "--write" in sys.argv:
        d = sys.argv[sys.argv.index("--write") + 1]
        os.makedirs(d, exist_ok=True)
        for name, data in files.items():
            with open(os.path.join(d, name), "wb") as f:
                f.write(data)
    json.dump(out, sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
