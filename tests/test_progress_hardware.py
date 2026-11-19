#!/usr/bin/env python3
"""The SDK rows of the progress report say how much of the SDK drives hardware (scripts/tools/progress.py). No game data, no compiler.

    row       a `hardware` range in sdk.txt gives the report a `hardware (from total)` row under SDK: counted from all the SDK's functions, not from one of the rows above it: the library functions inside it
              (1 of 4), whatever else is true of them
    beside    hardware is not one of the C states: a function is with C, object code only or not done, and it may be
              hardware as well. The three state rows are the same with the line as without it
    object    a hardware function that is byte-identical to the library is counted in both rows
    proven    a hardware function with proven C is counted in both rows: with C 2 of 4, hardware 1 of 4
    none      a repo with no `hardware` line has no such row
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
BASE = 0x8C010000
NAMES = ['libProven', 'kdDriver', 'libIdentical', 'libNothing']


def report(tmp, sdk, proven=('libProven',), identical=('libIdentical',)):
    def w(p, t):
        os.makedirs(os.path.dirname(os.path.join(tmp, p)) or tmp, exist_ok=True)
        with open(os.path.join(tmp, p), 'w') as fp:
            fp.write(t)
    w('functions.txt', ''.join('F %08x 8 %s\n' % (BASE + 8 * i, n) for i, n in enumerate(NAMES)))
    w('tests/equivalent.txt', ''.join(n + '\n' for n in proven))
    w('sdk.txt', 'range %08x %08x the library\n' % (BASE, BASE + 32) + sdk)
    w('sdk-identical.txt', '# identical\n' + ''.join('%s 8 lib.lib 0\n' % n for n in identical))
    w('status.txt', 'MODE: equivalent\n')
    r = subprocess.run([sys.executable, 'tools/progress.py'], cwd=tmp, capture_output=True, text=True)
    return r.stdout + r.stderr


def row(out, name):
    m = re.search(r'(?m)^  %s\s+[\d.]+%%\s+(\d+) of (\d+)' % re.escape(name), out)
    return (int(m.group(1)), int(m.group(2))) if m else None


class ProgressHardware(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='progress_hardware')
        self.addCleanup(shutil.rmtree, self.tmp, True)
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(self.tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        with open(os.path.join(self.tmp, '1ST_READ.BIN'), 'wb') as fp:
            fp.write(struct.pack('<16H', *([0x000B, 0x0009] * 8)))
        with open(os.path.join(self.tmp, 'BASE'), 'w') as fp:
            fp.write('%08X\n' % BASE)

    HW = 'hardware %08x %08x Maple bus driver\n' % (BASE + 8, BASE + 16)

    def test_row(self):
        out = report(self.tmp, self.HW)
        self.assertEqual(row(out, 'hardware (from total)'), (1, 4), out[-900:])

    def test_beside(self):
        with_line, without = report(self.tmp, self.HW), report(self.tmp, '')
        for name in ('with C', 'object code only', 'not done'):
            self.assertEqual(row(with_line, name), row(without, name), name)
        self.assertEqual(row(with_line, 'not done'), (2, 4), with_line[-900:])

    def test_object(self):
        out = report(self.tmp, self.HW, identical=('libIdentical', 'kdDriver'))
        self.assertEqual(row(out, 'hardware (from total)'), (1, 4), out[-900:])
        self.assertEqual(row(out, 'object code only'), (2, 4), out[-900:])

    def test_proven(self):
        out = report(self.tmp, self.HW, proven=('libProven', 'kdDriver'))
        self.assertEqual(row(out, 'with C'), (2, 4), out[-900:])
        self.assertEqual(row(out, 'hardware (from total)'), (1, 4), out[-900:])

    def test_none(self):
        out = report(self.tmp, '')
        self.assertIsNone(row(out, 'hardware (from total)'))
        self.assertEqual(row(out, 'not done'), (2, 4), out[-900:])

if __name__ == '__main__':
    unittest.main()
