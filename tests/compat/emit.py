#!/usr/bin/env python3
"""Synthetic inputs for the map tool's readers, and what the readers find in them, as JSON. Stdlib only.

    emit.py                  the readers' output on every input, JSON on stdout
    emit.py --write <dir>    also writes each input as a file in <dir> (a viewer's readers can then be run on the same bytes)

The inputs are built here from nothing: no game data, so they can be committed and run anywhere. They exercise the
formats the readers know (Sega PRS compression, PRS streams tagged PRESSED, object trees stored as a memory image, Ninja chunk models and motions,
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


def tree_fixture(base=0x8C100000):
    """Five objects in a chain (child, sibling, child, sibling) at a load address, one chunk model, one basic model."""
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


def flat_fixture():
    """One NAOMI-library flat model: a 24-byte part header (two counts, a sphere), then one record: a 0x50-byte header and
    one strip of 3 full vertices (position, normal, u, v)."""
    buf = bytearray((6 + 20 + 2 + 3 * 8) * 4)
    struct.pack_into("<2I3ff", buf, 0, 1, 1, 0.0, 0.0, 0.0, 5.0)                      # the part header: counts, sphere radius 5
    rec = 6 * 4
    struct.pack_into("<2I", buf, rec, 0x8000002C, 0x83000000)                          # control word, ISP word
    struct.pack_into("<i", buf, rec + 8 * 4, 7)                                        # the texture number
    struct.pack_into("<I", buf, rec + 19 * 4, (2 + 3 * 8) * 4)                         # the length of the strip data
    struct.pack_into("<2I", buf, rec + 20 * 4, 0x73, 3)                                # a strip: flags, three vertices
    for i in range(3):
        struct.pack_into("<8f", buf, rec + 22 * 4 + i * 32, float(i), 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)
    return bytes(buf)


def big_fixture():
    """A file of 20 MB (two stretches) holding a flat model, a Ninja chunk model and trees with different load addresses at
    known offsets: one in the first stretch only, one in the overlap of the two (found in both, kept once), one in the second
    stretch only. The trees' addresses are given by the file's first byte, so each stretch must report the same file."""
    mb = 1 << 20
    buf = bytearray(20 * mb)
    place = {2 * mb: flat_fixture(), 5 * mb: ninja_fixture(), 3 * mb: tree_fixture(0x8C300000 + 3 * mb),
             13 * mb: tree_fixture(0x8C300000 + 13 * mb), 17 * mb + 0x400: tree_fixture(0x8C300000 + 17 * mb + 0x400)}
    for off, data in place.items():
        buf[off:off + len(data)] = data
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


def quat_motion_fixture():
    """An NMDM motion with position and quaternion keys (a quaternion key is a frame and four floats) for one object, after a
    Ninja model of one object in the same file: the motion is found inside the file and its node count is the model's."""
    data = bytearray(108)
    struct.pack_into("<IIHH", data, 0, 12, 6, 0x2005, 3)
    struct.pack_into("<3I3I", data, 12, 36, 68, 0, 2, 2, 0)
    struct.pack_into("<I3f", data, 36, 0, 0.0, 0.0, 0.0)
    struct.pack_into("<I3f", data, 52, 6, 1.0, 2.0, 3.0)
    struct.pack_into("<I4f", data, 68, 0, 1.0, 0.0, 0.0, 0.0)
    struct.pack_into("<I4f", data, 88, 6, 0.7071, 0.0, 0.7071, 0.0)
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


def pressed_fixture():
    """Three tagged PRS streams: one with a size and a name (the size right), one with the tag and the stream only, and a tag
    at the end whose stream does not decompress (passed over); a tag whose size is wrong is passed over too, its stream
    being read as the second layout."""
    def stream(plain):
        e = Prs()
        e.literal(plain)
        return e.end()
    a, b, c = flat_fixture(), ninja_fixture(), b"wrong size"
    return (b"junk" + b"PRESSEDPOLFORMAT" + struct.pack(">I", len(a)) + b"model_a".ljust(12, b"\x00") + stream(a)
            + b"\x00\x00" + b"PRESSEDPVRFORMAT" + stream(b)
            + b"PRESSEDPOLFORMAT" + struct.pack(">I", 99) + b"bad".ljust(12, b"\x00") + stream(c)
            + b"PRESSEDPVRFORMAT" + b"\xff" * 8)


def sound_fixtures():
    """An AFS archive (an ADX stream, something else, an AHX stream), a file that is one ADX stream, an archive of other things
    (no rows), and a DTPK sound bank."""
    def adx(enc, ch, rate, samples):
        return b"\x80\x00\x00\x20" + bytes([enc, 18, 4, ch]) + struct.pack(">II", rate, samples) + b"\x00" * 16
    entries = [adx(3, 2, 44100, 441000), b"not audio at all!!", adx(0x10, 1, 22050, 22050)]
    table, off = b"AFS\x00" + struct.pack("<I", 3), 0x800
    body = b""
    for e in entries:
        table += struct.pack("<II", off + len(body), len(e))
        body += e.ljust((len(e) + 15) // 16 * 16, b"\x00")
    afs = table.ljust(off, b"\x00") + body
    other = b"AFS\x00" + struct.pack("<I", 1) + struct.pack("<II", 0x10, 20) + b"not audio at all!!!!"
    return {"snd_afs.bin": afs, "snd_adx.bin": adx(3, 1, 32000, 64000), "snd_other.bin": other, "snd_dtpk.bin": b"DTPK" + b"\x00" * 60}


def own_textures_fixture():
    """A file holding two Ninja models with their textures: NJTL (2 names) and NJCM, NJTL (1 name) and NJCM, then 3 PVR chunks
    (a GBIX header and a PVRT each); the names, joined, count the chunks."""
    def njtl(names):
        tl = struct.pack("<II", 8, len(names))
        tl += b"".join(struct.pack("<3I", 8 + 12 * len(names) + 8 * i, 0, 0) for i in range(len(names)))
        return b"NJTL" + struct.pack("<I", len(tl) + 8 * len(names)) + tl + b"".join(n.ljust(8, b"\x00") for n in names)

    def njcm():
        cm = bytearray(0x4C)
        struct.pack_into("<II3f3i3fII", cm, 0, 0, 0x34, 0.0, 0.0, 0.0, 0, 0, 0, 1.0, 1.0, 1.0, 0, 0)
        struct.pack_into("<II3ff", cm, 0x34, 0, 0, 0.0, 0.0, 0.0, 3.5)
        return b"NJCM" + struct.pack("<I", len(cm)) + bytes(cm)

    def pvr(w, h):
        body = w * h * 2
        return b"GBIX" + struct.pack("<II", 8, 0) + b"PVRT" + struct.pack("<I", body + 8) + bytes([1, 1, 0, 0]) + struct.pack("<2H", w, h) + b"\x00" * body
    return b"\x00" * 4 + njtl([b"texa", b"texb"]) + njcm() + njtl([b"texc"]) + njcm() + pvr(8, 8) + pvr(16, 8) + pvr(8, 16)


def own_texture_fixture():
    """A file holding two Ninja models and their textures: a name list (two names), a model, a name list (one name), a model,
    then three PVR textures. Returns (bytes, the two models' offsets)."""
    def njtl(names):
        tail = b"".join(n + b"\x00" for n in names)
        head = struct.pack("<II", 8, len(names))
        offs, at = [], 8 + 12 * len(names)
        for n in names:
            offs.append(at)
            at += len(n) + 1
        body = (head + b"".join(struct.pack("<3I", o, 0, 0) for o in offs) + tail).ljust((8 + 12 * len(names) + len(tail) + 3) // 4 * 4, b"\x00")
        return b"NJTL" + struct.pack("<I", len(body)) + body
    def njcm():
        cm = bytearray(0x4C)
        struct.pack_into("<II3f3i3fII", cm, 0, 0, 0x34, 0.0, 0.0, 0.0, 0, 0, 0, 1.0, 1.0, 1.0, 0, 0)
        struct.pack_into("<II3ff", cm, 0x34, 0, 0, 0.0, 0.0, 0.0, 6.5)
        return b"NJCM" + struct.pack("<I", len(cm)) + bytes(cm)
    def pvrt(w, h):
        body = w * h * 2
        return b"PVRT" + struct.pack("<I", body + 8) + bytes([1, 1, 0, 0]) + struct.pack("<2H", w, h) + b"\x00" * body
    data = b"CGAM" + b"\x00" * 12
    first = len(data) + len(njtl([b"ta", b"tb"]))
    data += njtl([b"ta", b"tb"]) + njcm()
    second = len(data) + len(njtl([b"tc"]))
    data += njtl([b"tc"]) + njcm()
    return data + pvrt(8, 8) + pvrt(16, 8) + pvrt(8, 16), [first, second]


def results(mm):
    out, files = {}, {}
    for name, (stream, plain) in prs_fixtures().items():
        files[name] = stream
        got = mm.prs_decompress(stream)
        assert got == plain, name + ": the PRS reader does not give back what the test encoder put in"
        out["prs:" + name] = {"bytes": len(got), "hex": got[:48].hex()}
    files["flat.bin"] = flat = flat_fixture()
    out["flat:flat.bin"] = [[o, r, n, round(rad, 3), tex] for o, r, n, rad, tex in mm.find_models(flat)]
    files["tree.bin"] = tree = tree_fixture()
    trees, base = mm.find_object_trees(tree)
    out["trees:tree.bin"] = {"base": base, "trees": [[o, n, round(r, 3)] for o, n, r in trees]}
    files["ninja.bin"] = nj = ninja_fixture()
    out["ninja:ninja.bin"] = [[o, nb, objs, round(r, 3), names] for o, nb, objs, r, names in mm.find_ninja(nj)]
    files["motion.njm"] = mo = motion_fixture()
    r = mm.njm_read(mo, 2)
    out["motion:motion.njm"] = [r[0], r[1], r[2], r[3]] if r else None
    for name, data in sound_fixtures().items():
        files[name] = data
        out["sounds:" + name] = [list(r) for r in mm.audio_file_rows(len(data), data[:4096], lambda o, n, d=data: d[o:o + n])]
    files["own_tex.bin"] = ot = own_textures_fixture()
    nj_ot = mm.find_ninja(ot)
    got = mm.own_textures(ot, [m[0] for m in nj_ot])
    out["own_textures:own_tex.bin"] = {"models": [[m[0], m[2]] for m in nj_ot],
                                       "rows": [list(r) for r in got[0]] if got else None,
                                       "sets": sorted([list(x) for x in got[1].items()]) if got else None}
    files["pressed.bin"] = pr = pressed_fixture()
    out["pressed:pressed.bin"] = [[at, name, len(dec), dec[:48].hex(), end] for at, name, dec, end in mm.pressed_blocks(pr)]
    files["owntex.bin"], offs = own_texture_fixture()
    got = mm.own_textures(files["owntex.bin"], offs)
    out["owntextures:owntex.bin"] = [[list(r) for r in got[0]], sorted(got[1].items())] if got else None
    files["motion_q.njm"] = mq = quat_motion_fixture()
    r = mm.njm_read(mq, 1)
    out["motion:motion_q.njm"] = [r[0], r[1], r[2], r[3]] if r else None
    files["embedded.bin"] = emb = ninja_fixture().ljust(256, b"\x00") + mq
    out["motions:embedded.bin"] = [list(m) for m in mm.find_motions(emb)]
    files["big.bin"] = big = big_fixture()
    flatm, trees_m, nj_m = mm.scan_buffer(big)
    out["scan:big.bin"] = {"flat": [[o, r, n, round(rad, 3), tex] for o, r, n, rad, tex in flatm],
                           "trees": [[o, n, round(rad, 3), fb] for o, n, rad, fb in trees_m],
                           "ninja": [[o, nb, objs, round(rad, 3), names] for o, nb, objs, rad, names in nj_m]}
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
