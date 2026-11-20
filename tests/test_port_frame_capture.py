#!/usr/bin/env python3
"""The native game's frame, read from its memory (scripts/tools/10-port/frame_capture.py): the renderer's records laid out as
pvr.c lays them (struct tabuf, struct poly, struct rvert), built here in a fake memory. No game, no compiler. Stdlib only.

    last       of the four buffers, the one before the newest is read (the newest may still be filling)
    polygons   each polygon's list, control words and vertices come out as stored
    text       the text form: a header line, then one line per polygon with its vertices
    empty      a frame with no polygons (a loading screen) reads as empty, nothing read past the records
    short      a polygon whose vertices run past the buffer's count (a frame cut while it filled) keeps only the ones there
"""
import importlib.util
import os
import struct
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'scripts', 'tools', '10-port', 'frame_capture.py')


def load():
    spec = importlib.util.spec_from_file_location('frame_capture', TOOL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class FakeMemory:
    def __init__(self):
        self.blocks = {}

    def put(self, a, data):
        self.blocks[a] = data

    def read(self, a, n):
        for base, data in self.blocks.items():
            if base <= a and a + n <= base + len(data):
                return data[a - base:a - base + n]
        raise AssertionError('read outside the fake memory: %#x + %d' % (a, n))


class FrameCapture(unittest.TestCase):
    def setUp(self):
        self.fc = load()
        self.mem = FakeMemory()
        bufs, polys, verts = 0x1000, 0x2000, 0x3000
        tabs = b''
        for i, frame in enumerate((7, 9, 8, 6)):              # buffer 1 is newest (frame 9): buffer 2 (frame 8) is read
            np_ = 2 if i == 2 else 0
            nv = 4 if i == 2 else 0
            tabs += struct.pack('<I4xQIIQIIQ', 0, verts, nv, 64, polys, np_, 64, frame)
        self.mem.put(bufs, tabs)
        self.mem.put(polys, struct.pack('<4IIIi', 0x808C002C, 0x93000000, 0x2008246C, 0x080BF9B8, 0, 3, 0)
                     + struct.pack('<4IIIi', 0x828C002C, 0x8B000000, 0x9408A45B, 0xC80BF80C, 3, 1, 2))
        rv = lambda x, y, w: struct.pack('<5fIIfI', x, y, w, 0, 0, 0, 0, 0, 0)
        self.mem.put(verts, rv(248.3, 362.6, 36.8) + rv(684.9, 372.4, 28.58) + rv(-32584.2, 4481.6, 0.3) + rv(1, 2, 3))
        self.bufs = bufs

    def test_last(self):
        frame, buf, polys = self.fc.last_frame(self.mem.read, self.bufs)
        self.assertEqual((frame, buf), (8, 2), 'the buffer before the newest one')

    def test_polygons(self):
        frame, buf, polys = self.fc.last_frame(self.mem.read, self.bufs)
        self.assertEqual(len(polys), 2)
        k, lst, pcw, isp, tsp, tcw, vs = polys[1]
        self.assertEqual((k, lst, pcw, isp, tsp, tcw), (1, 2, 0x828C002C, 0x8B000000, 0x9408A45B, 0xC80BF80C), 'control words as stored')
        self.assertEqual(len(vs), 1)
        self.assertAlmostEqual(vs[0][2], 3.0, msg='the vertex after the first polygon\'s three')
        self.assertAlmostEqual(polys[0][6][2][0], -32584.2, places=1, msg='a far corner kept as it is')

    def test_text(self):
        frame, buf, polys = self.fc.last_frame(self.mem.read, self.bufs)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, 'f.txt')
            self.fc.write_frame(p, frame, buf, polys)
            lines = open(p).read().splitlines()
        self.assertEqual(lines[0], 'frame 8 buffer 2: 2 polygons, 4 vertices')
        self.assertTrue(lines[1].startswith('poly 0 list 0 pcw 808C002C isp 93000000 tsp 2008246C tcw 080BF9B8 n 3  (248.3 362.6 w36.8)'),
                        'a polygon line: %s' % lines[1])
        self.assertEqual(len(lines), 3, 'a header and one line per polygon')

    def test_empty(self):
        mem = FakeMemory()
        mem.put(0x1000, b''.join(struct.pack('<I4xQIIQIIQ', 0, 0, 0, 0, 0, 0, 0, f) for f in (3, 4, 1, 2)))
        frame, buf, polys = self.fc.last_frame(mem.read, 0x1000)
        self.assertEqual((frame, buf, polys), (3, 0, []), 'the buffer before the newest, no polygons, nothing read beyond')

    def test_short(self):
        mem = FakeMemory()
        tabs = b''
        for i, frame in enumerate((2, 1, 3, 0)):              # buffer 0 (frame 2) is read: one polygon of 3 vertices, 2 there
            tabs += struct.pack('<I4xQIIQIIQ', 0, 0x3000, 2 if i == 0 else 0, 8, 0x2000, 1 if i == 0 else 0, 8, frame)
        mem.put(0x1000, tabs)
        mem.put(0x2000, struct.pack('<4IIIi', 1, 2, 3, 4, 0, 3, 0))
        mem.put(0x3000, struct.pack('<5fIIfI', 10, 20, 5, 0, 0, 0, 0, 0, 0) * 2)
        frame, buf, polys = self.fc.last_frame(mem.read, 0x1000)
        self.assertEqual(len(polys[0][6]), 2, 'only the vertices the buffer holds')


if __name__ == '__main__':
    unittest.main()
