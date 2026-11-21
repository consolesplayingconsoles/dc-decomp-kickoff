#!/usr/bin/env python3
"""Which words of the listed code are literal pools (scripts/tools/8-build/shift.py _listed()). No game data, no compiler. Stdlib only.

A listed function's size can cover its own literal pool, and a pool long is stored as two halfwords. One half can look like a
`mov.l @(disp,pc),Rn` (0xD???) or a `mova` (0xC7??), so reading every halfword of the listed bytes as an instruction adds a pool
word of its own: the word it points at, which can be two instructions of the next function. Pointers.py then takes those two
instructions for an address and the build rewrites them as a symbol.

    check.py      a temp repo: f1 loads a pool long whose low half is 0xD205 (mov.l @(5,pc),r2), f1's listed size covers that
                  pool, f2 follows with two instructions where 0xD205 would point:
                    literal   the long f1 loads is a pool word, and its halves are not instructions
                    ghost     the word 0xD205 would point at (in f2's code) is not a pool word
"""
import unittest
from unittest import mock
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
BASE = 0x0C010000
W = lambda *h: struct.pack('<%dH' % len(h), *h)
L = lambda *v: struct.pack('<%dI' % len(v), *v)

CODE = (W(0xD101, 0x000B, 0x0009, 0x0009) +          # 00 f1: mov.l @(1,pc),r1 (loads the long at 08) / rts / nop / pad
        L(0x0C0ED205) +                                # 08 the pool long: its low half 0xD205 reads as mov.l @(5,pc),r2
        W(0x0009, 0x0009, 0x0009, 0x0009) +            # 0C pad: f1 is listed as 0x0C bytes, f2 starts at 10
        W(0x0009, 0x0009, 0x0009, 0x0009, 0x0009, 0x0009, 0x0009, 0x0009) +    # 10 f2: nops
        W(0x7204, 0x0C1A) +                            # 20 two instructions (add #4,r2 / sts macl,r12): where 0xD205 would point
        W(0x000B, 0x0009))                             # 24 rts / nop
IMAGE = CODE + b'\0' * (0x200 - len(CODE))


class TestShiftpool(unittest.TestCase):
    def setUp(self):
        self.addCleanup(os.chdir, os.getcwd())
        saved_path = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        environ = mock.patch.dict(os.environ)
        environ.start()
        self.addCleanup(environ.stop)

    def test_shiftpool(self):
        bad = []
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
            open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(IMAGE)
            open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
            open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x 12 f1\nF %08x 40 f2\n' % (BASE, BASE + 0x10))
            open(os.path.join(tmp, 'layout.txt'), 'w').write('game 0C010000 0C010200\nkeep 0C010100 0C010200\nshift 00010000 0C100000\n')
            script = ("import sys; sys.path.insert(0, 'tools'); sys.path.insert(0, 'tools/8-build'); import toolpath, shift\n"
                      "print(' '.join('%x' % (a - 0x0C010000) for a in sorted(shift._listed()[2])))\n")
            r = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
            pools = r.stdout.strip().split('\n')[-1].split()
            if '8' not in pools:
                bad.append('literal: the long f1 loads (+8) is not a pool word: %r\n%s' % (pools, r.stdout[-400:]))
            if '20' in pools:
                bad.append('ghost: +20 (two instructions of f2) is a pool word, taken from the half 0xD205 of the long at +8: %r' % pools)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if bad:
            self.fail('[ERROR] shiftpool check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
