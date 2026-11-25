#!/usr/bin/env python3
"""A function whose argument only indexes a table gets cases a list walk ends on (scripts/tools/5-generated/gen_equiv/gen_drv.py tests).
No game data, no compiler. Stdlib only.

A parameter that appears in an address was drawn as an address (0x0C800000, memory filled behind it). One that is only scaled there
(`a4 << 3`, `a4 * 12`) is an index: drawn as an address, the table entry it picks lay far past any filled memory, read 0, and the list
walked from that 0 never held a negative word. Every drawn case ran to the step limit and the function was skipped, "the original does
not finish on the cases" (178 of 179 runs).

    check.py      a function in a temp repo (`r2 = *G + 4; r2 = *(r2 + a * 8); while (*r2 >= 0) r2++; return 0`):
                    drawn     tests() returns cases for it, at least twelve
"""
import unittest
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
BASE = 0x0C010000
GLOBAL = 0x8C2E4AF8
W = lambda ws: b''.join(struct.pack('<H', w) for w in ws)

WORDS = [0xD107,        # mov.l @(pool,pc),r1      the address of the global
         0x6212,        # mov.l @r1,r2             the table's base
         0x7204,        # add #4,r2
         0x6043,        # mov r4,r0
         0x4008,        # shll2 r0
         0x4000,        # shll r0                  a * 8
         0x022E,        # mov.l @(r0,r2),r2        the list the entry names
         0x6022,        # L: mov.l @r2,r0
         0x4011,        # cmp/pz r0
         0x8B02,        # bf out
         0x7204,        # add #4,r2
         0xAFFA,        # bra L
         0x0009,        # nop
         0x000B,        # out: rts
         0xE000,        # mov #0,r0
         0x0009,
         GLOBAL & 0xFFFF, GLOBAL >> 16]


class TestListWalk(unittest.TestCase):
    def test_listwalk(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        code = W(WORDS)
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d f\n' % (BASE, len(code)))
        os.makedirs(os.path.join(tmp, 'src'))
        script = ("import sys; sys.path.insert(0, 'tools'); sys.path.insert(0, 'tools/5-generated/gen_equiv'); import toolpath, gen_core, gen_drv, gen_pipe\n"
                  "try:\n"
                  "    v = gen_pipe.variants('f', False)[0]\n"
                  "    src, c = gen_drv.build('f', v, False)\n"
                  "    t = gen_drv.tests('f', c, src)\n"
                  "    print('CASES', len(t['dev']) + len(t['holdout']))\n"
                  "except gen_core.Skip as e:\n"
                  "    print('SKIPPED ' + str(e))\n")
        # drawing stops at a wall-clock deadline (a third of a minute for a function this small), so on a loaded machine it kept three cases
        # and the check failed: the check is what is drawn, not how fast
        env = dict(os.environ, GEN_DRAW_SECONDS='900')
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        lines = [l for l in out.splitlines() if l.startswith(('CASES', 'SKIPPED'))]
        n = int(lines[0].split()[1]) if lines and lines[0].startswith('CASES') else 0
        if n < 12:
            self.fail('[ERROR] listwalk check failed: %s' % (lines[0] if lines else out[-400:]))


if __name__ == '__main__':
    unittest.main()
