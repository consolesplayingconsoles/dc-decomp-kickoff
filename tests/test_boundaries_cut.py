#!/usr/bin/env python3
"""The size a function is cut to when a new entry starts inside its listed size (scripts/tools/common/boundaries.py main(), cuts).
No game data, no compiler. Stdlib only.

A listed function can span several routines the analysis merged: its code, a small routine g, and a routine t it reaches by a tail
`bra`. When g is listed, the holder is cut to what it reaches by its own branches, and a `bra` to another entry is a tail jump, not
more of the holder. The cut walked the holder without that rule, followed the `bra` to t (a candidate in the same list, not yet an
entry), and kept the holder's size: the holder still overlapped g and t (Power Stone 2 FUN_0c0e9ada 1948 bytes over FUN_0c0ea19e and
0C0EA1F8). A candidate of the same run counts as an entry for that rule.

    check.py      a temp repo: h (tst, bf over a `bra t`, rts) with a listed size that covers g and t, g and t candidates, f2 after:
                    plan      g and t are "function"; one entry is cut
                    cut       with --apply, h's line holds its own 12 bytes, and g and t are listed after it
                    tail      a holder with no tail jump to a candidate keeps what it reaches
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
BASE = 0x8C010000
NOP, RTS = 0x0009, 0x000B


def w(*ws):
    return b''.join(struct.pack('<H', x) for x in ws)


def bra_to(at, target):
    return 0xA000 | (((target - (at + 4)) // 2) & 0xFFF)


def run(code, functions, cands):
    tmp = tempfile.mkdtemp(prefix='boundaries_cut_')
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        for name, data, mode in (('1ST_READ.BIN', code, 'wb'), ('BASE', '%08X\n' % BASE, 'w'), ('functions.txt', functions, 'w'),
                                 ('cands.txt', ''.join('%08x\n' % c for c in cands), 'w')):
            with open(os.path.join(tmp, name), mode) as fh:
                fh.write(data)
        r = subprocess.run([sys.executable, 'tools/common/boundaries.py', 'cands.txt', '--apply'], cwd=tmp, capture_output=True, text=True, timeout=120)
        with open(os.path.join(tmp, 'functions.txt')) as fh:
            return r.stdout + r.stderr, fh.read()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class TestBoundariesCut(unittest.TestCase):
    def layout(self, tail):
        h_at = BASE
        g_at = h_at + 12                                       # h is 6 words
        t_at = g_at + 12                                       # g is 4 words, then 2 pad words
        f2_at = t_at + 12                                      # t is 4 words, then 2 pad words
        # h: tst r4,r4 / bf +4 (to the rts) / bra t or bra +0 / nop / rts / nop
        body = w(0x2448, 0x8B01, bra_to(h_at + 4, t_at if tail else h_at + 8), NOP, RTS, NOP)
        g = w(0x4F22, 0x4F26, RTS, NOP)                       # push pr / pop pr / rts: a function
        t = w(0x4F22, 0x4F26, RTS, NOP)
        pad = w(NOP, NOP)                                      # a pool-sized gap after g, so g and t do not run together
        code = body + g + pad + t + pad + w(RTS, NOP)
        return h_at, g_at, t_at, code, f2_at

    def test_cut(self):
        h_at, g_at, t_at, code, f2_at = self.layout(True)
        functions = 'F %08x %d h\nF %08x 4 f2\n' % (h_at, f2_at - h_at, f2_at)
        out, after = run(code, functions, [g_at, t_at])
        self.assertIn('2 new functions, 1 entries cut', out, out)
        lines = [l.split() for l in after.splitlines() if l.startswith('F ')]
        by = {int(l[1], 16): l for l in lines}
        self.assertEqual(int(by[h_at][2]), 12, 'h is cut to its own 12 bytes: %s' % after)
        self.assertIn(g_at, by)
        self.assertIn(t_at, by)

    def test_no_tail(self):
        h_at, g_at, t_at, code, f2_at = self.layout(False)
        functions = 'F %08x %d h\nF %08x 4 f2\n' % (h_at, f2_at - h_at, f2_at)
        out, after = run(code, functions, [g_at, t_at])
        by = {int(l.split()[1], 16): l.split() for l in after.splitlines() if l.startswith('F ')}
        self.assertEqual(int(by[h_at][2]), 12, after)         # nothing reaches t from h: the same cut


if __name__ == '__main__':
    unittest.main()
