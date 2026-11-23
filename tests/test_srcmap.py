#!/usr/bin/env python3
"""srcmap.py (scripts/tools/5-generated/srcmap.py): the original source files of an executable, found from its code alone. No game data. Stdlib only.

A source file is a run of functions in link order. Two functions are of one file when one reads a literal-pool word placed inside the other
(`mov.l @(addr,pc)`, `mova`), calls it with `bsr`, or branches into it; every function between them is of that file too. A cell that starts at an
address that is 2 mod 4 joins the one before it (a file starts 4-aligned).

    check.py      pool       a literal read inside the next function:                  one cell of the two
                  chain      a bsr two functions on:                                    the one between is in the cell
                  alone      a branch inside its own function:                          no tie
                  aligned    a cell starting at 2 mod 4:                                joined to the one before
                  rows       the file srcmap writes:                                    start end count first last, end exclusive
"""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools', '5-generated'))
import srcmap  # noqa: E402

FUNCS = [(0x1000, 0x20, 'A'), (0x1020, 0x20, 'B'), (0x1040, 0x20, 'C'), (0x1060, 0x22, 'D'), (0x1082, 0x20, 'E')]


def ins(pc, text):
    return '%08x 0000  %s' % (pc, text)


class TestSrcmap(unittest.TestCase):
    def names(self, dis, funcs=FUNCS):
        cells, links = srcmap.build_cells(funcs, '\n'.join(dis))
        return [(funcs[i][2], funcs[j][2]) for i, j in cells], links

    def test_pool(self):
        got, links = self.names([ins(0x1004, 'mov.l   @(0x00001030,pc),r1')])
        self.assertEqual(got[0], ('A', 'B'))
        self.assertEqual(links, 1)

    def test_chain(self):
        got, _ = self.names([ins(0x1000, 'bsr     0x00001040'), ins(0x1002, 'mova    @(0x00001050,pc),r0')])
        self.assertEqual(got[0], ('A', 'C'))                      # B is between

    def test_alone(self):
        got, links = self.names([ins(0x1004, 'bra     0x00001010')])
        self.assertEqual(links, 0)
        self.assertEqual(got[0], ('A', 'A'))

    def test_aligned(self):
        got, _ = self.names([])
        self.assertEqual(got, [('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'E')])

    def test_rows(self):
        d = tempfile.mkdtemp()
        old = os.getcwd()
        self.addCleanup(os.chdir, old)
        os.chdir(d)
        with open('functions.txt', 'w') as fh:
            fh.write(''.join('F %x %d %s\n' % (a, n, name) for a, n, name in FUNCS))
        srcmap.write_cells(FUNCS, [(0, 1), (2, 4)], os.path.join(d, 'out', 'cells.tsv'))
        with open(os.path.join(d, 'out', 'cells.tsv')) as fh:
            rows = [l.split('\t') for l in fh.read().splitlines() if not l.startswith('#')]
        self.assertEqual(rows, [['00001000', '00001040', '2', 'A', 'B'], ['00001040', '000010a2', '3', 'C', 'E']])


if __name__ == '__main__':
    unittest.main()
