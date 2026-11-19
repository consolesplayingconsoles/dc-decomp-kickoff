#!/usr/bin/env python3
"""The report's "no C form" count is the game's own functions (scripts/tools/progress.py). No game data, no compiler.

    game      two functions use an instruction with no C form (`stc ssr,r0`): one is the game's, one is inside a library
              range of sdk.txt. The report says 1 with no C form: the library's is the SDK's, counted in the SDK rows
              ("not done"), not among the game's (Crazy Taxi showed 54 where 8 are the game's)
    total     the functions that can be C are counted as before: the library's function is still not among them
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
PLAIN = [0x000B, 0x0009, 0x0009, 0x0009]            # rts; nop
NO_C = [0x0032, 0x000B, 0x0009, 0x0009]             # stc ssr,r0; rts; nop
NAMES = ['gameDone', 'gameNoC', 'libNoC', 'libPlain']


class ProgressNoCFormGame(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='progress_nocform')
        self.addCleanup(shutil.rmtree, self.tmp, True)
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(self.tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))

        def w(p, t, mode='w'):
            os.makedirs(os.path.dirname(os.path.join(self.tmp, p)) or self.tmp, exist_ok=True)
            with open(os.path.join(self.tmp, p), mode) as fp:
                fp.write(t)
        w('1ST_READ.BIN', struct.pack('<16H', *(PLAIN + NO_C + NO_C + PLAIN)), 'wb')
        w('BASE', '%08X\n' % BASE)
        w('functions.txt', ''.join('F %08x 8 %s\n' % (BASE + 8 * i, n) for i, n in enumerate(NAMES)))
        w('tests/equivalent.txt', 'gameDone\n')
        w('sdk.txt', 'range %08x %08x the library\n' % (BASE + 16, BASE + 32))
        w('status.txt', 'MODE: equivalent\n')
        r = subprocess.run([sys.executable, 'tools/progress.py'], cwd=self.tmp, capture_output=True, text=True)
        self.out = r.stdout + r.stderr

    def test_game(self):
        m = re.search(r'\((\d+) with no C form are counted apart\)', self.out)
        self.assertTrue(m, self.out[-800:])
        self.assertEqual(int(m.group(1)), 1, self.out[-800:])

    def test_total(self):
        m = re.search(r'FUNCTIONS LEFT\s+\(\s*[\d.]+% complete\)\s+(\d+)\s+of the (\d+) functions', self.out)
        self.assertTrue(m, self.out[-800:])
        self.assertEqual((int(m.group(1)), int(m.group(2))), (1, 2), self.out[-800:])


    def test_sdk(self):
        """sdk: the SDK rows follow the same pattern: the library's function with no C form is its own row, counted apart,
        and the other rows are of what can be C and add up to 100%. Here the library has two functions: one with no C form, one
        not done, so `not done` is 1 of 1 (100%: the rows add up to all that can be C) and `no C form` is a percentage, as the game's row is: 50.0%, 1 of the library's 2"""
        def row(name):
            m = re.search(r'(?m)^  %s\s+[\d.]+%%\s+(\d+) of (\d+)' % re.escape(name), self.out)
            return (int(m.group(1)), int(m.group(2))) if m else None
        m = re.search(r'(?m)^  no C form\s+([\d.]+)%\s+an instruction or a register convention with no C form', self.out)
        self.assertTrue(m, self.out[-800:])
        self.assertEqual(float(m.group(1)), 50.0, self.out[-800:])        # as the game's row: a share of all its functions
        self.assertEqual(row('not done'), (1, 1), self.out[-800:])
        self.assertEqual(row('with C'), (0, 1), self.out[-800:])


    def test_heading(self):
        """heading: the SDK heading gives no total, as the game's block gives none: the rows say what they are of"""
        m = re.search(r'(?m)^SDK\b(.*)$', self.out)
        self.assertTrue(m, self.out[-800:])
        self.assertEqual(m.group(1).strip(), '', self.out[-800:])


if __name__ == '__main__':
    unittest.main()
