#!/usr/bin/env python3
"""A piece after a long data tail stays with the piece that owns the tail (scripts/tools/1-2-baseline/movecheck.py groups(), data_tail).
No game data, no compiler, no simulator. Stdlib only.

A listed function owns every byte up to the next listed one: its code, then its literal pool, then whatever data the link order put
after it. When that tail is long (a data section, tables), the piece after it begins where the data ends, and an address word that
marks the END of a data section is the same number as the START of that piece. The two cannot be told apart in the split, and the
word is written as the later piece's label, so a pad between the pieces lengthens the section the start-up code copies or clears
(Power Stone 2 _INITSCT: the data section 0C2AE8F4-0C2AE900 became 44 bytes; the copy ran on into the next function). Keeping the
two pieces together keeps that distance. Pieces closer than data_tail (default 2 KB: pools and padding) are not tied by this.

    check.py      long      f1 (0x10 bytes) then f2 0x1000 on:                          one group
                  short     f1 then f2 0x400 on:                                        two groups
                  edge      a tail of exactly 0x800 is not tied, 0x802 is
                  off       data_tail=None: the old grouping
                  last      the last piece has no next one: nothing to tie, no error
                  chain     a long tail after each of three functions:                  one group
                  merge     random layouts: with the rule the group starts are a subset of the old ones (it only merges)
"""
import os
import random
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(SKILL, 'scripts', 'tools', '1-2-baseline'))
sys.path.insert(0, os.path.join(SKILL, 'scripts', 'tools'))
B0 = 0x0C010000


class TestTail(unittest.TestCase):
    def setUp(self):
        self.addCleanup(os.chdir, os.getcwd())
        saved = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        os.chdir(tmp.name)                       # layout.py reads layout.txt from the working directory: none here
        import movecheck
        self.M = movecheck

    def groups(self, offsets, size=0x10, **kw):
        """groups() of listed functions of `size` bytes at the offsets, each closing with an rts (so none runs into the next piece)"""
        starts = [B0 + o for o in offsets]
        code = [(a, size) for a in starts]
        closes = {a + size - 4: 0x000B for a in starts}
        return self.M.groups(starts, set(starts), code, lambda a: closes.get(a, 0x0009), set(), B0 + offsets[-1] + 0x100, **kw)

    def test_long(self):
        self.assertEqual(self.groups([0, 0x1010]), [0])

    def test_short(self):
        self.assertEqual(self.groups([0, 0x410]), [0, 1])

    def test_edge(self):
        self.assertEqual(self.groups([0, 0x10 + 0x800]), [0, 1])
        self.assertEqual(self.groups([0, 0x10 + 0x802]), [0])

    def test_off(self):
        self.assertEqual(self.groups([0, 0x1010], data_tail=None), [0, 1])

    def test_last(self):
        self.assertEqual(self.groups([0x1000]), [0])

    def test_chain(self):
        self.assertEqual(self.groups([0, 0x1010, 0x2020]), [0])

    def test_merge(self):
        rng = random.Random(3)
        for _ in range(300):
            offs, o = [], 0
            for _ in range(rng.randint(2, 9)):
                offs.append(o)
                o += 0x10 + rng.choice([0, 0x10, 0x100, 0x7F0, 0x800, 0x900, 0x2000])
            new = self.groups(offs)
            old = self.groups(offs, data_tail=None)
            self.assertTrue(set(new) <= set(old), '%s: %s is not a subset of %s' % (offs, new, old))
            self.assertEqual(new[0], 0)


if __name__ == '__main__':
    unittest.main()
