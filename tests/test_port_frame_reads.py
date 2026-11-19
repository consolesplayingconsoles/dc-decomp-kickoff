#!/usr/bin/env python3
"""Functions whose C reads past its own local frame (scripts/tools/10-port/frame_reads.py).
No game data, no compiler. Stdlib only.

    offsets    the constant offsets a body takes from its frame: `(int)stk + 8`, `((int)stk) + 0x10`, `4 + (int)stk`,
               and a sum of two constants `(int)stk + 8 + 4` is 12
    past       a temp src/ with a function of `int stk[3]` (12 bytes) that reads `(int)stk + 12` is listed with its frame size
               and the largest offset: that word is its caller's, a stack argument the C does not declare
    inside     a function that stays inside its frame (`int stk[4]`, reads + 12) is not listed
    noframe    a function with no `stk` is not listed
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')

SRC = '''int past(int a4)
{
    int stk[3];
    int t0;
    t0 = *(int *)((int)stk + 12);
    return t0 + *(int *)((int)stk + 4);
}

int inside(int a4)
{
    int stk[4];
    return *(int *)((int)stk + 12);
}

int noframe(int a4)
{
    return a4 + 12;
}
'''


def load(src_dir):
    """frame_reads.py reads PORT_SRC when it is imported: a fresh module for each folder"""
    with mock.patch.dict(os.environ, {'PORT_SRC': src_dir}):
        spec = importlib.util.spec_from_file_location('frame_reads_under_test', os.path.join(TOOLS, '10-port', 'frame_reads.py'))
        mod = importlib.util.module_from_spec(spec)
        saved = list(sys.path)
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.path[:] = saved
    return mod


class FrameReads(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='frame_reads')
        self.addCleanup(shutil.rmtree, self.tmp, True)
        with open(os.path.join(self.tmp, 'a.c'), 'w') as fp:
            fp.write(SRC)
        self.mod = load(self.tmp)

    def test_offsets(self):
        o = self.mod.offsets
        self.assertEqual(o('x = *(int *)((int)stk + 8);'), [8])
        self.assertEqual(o('x = *(int *)(((int)stk) + 0x10);'), [16])
        self.assertEqual(o('x = *(int *)(4 + (int)stk);'), [4])
        self.assertEqual(o('x = *(int *)((int)stk + 8 + 4);'), [12])

    def test_past(self):
        self.assertIn(('a.c', 'past', 12, 12), self.mod.scan())

    def test_inside(self):
        self.assertNotIn('inside', [r[1] for r in self.mod.scan()])

    def test_noframe(self):
        self.assertNotIn('noframe', [r[1] for r in self.mod.scan()])


if __name__ == '__main__':
    unittest.main()
