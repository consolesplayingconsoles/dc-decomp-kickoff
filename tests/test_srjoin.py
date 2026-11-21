#!/usr/bin/env python3
"""The two arms of an if each build the next interrupt mask from SR and an argument, and one `ldc r0,sr` after the join sets it
(scripts/tools/5-generated/gen_equiv/gen_core.py, the if / else join). The status-register value of each arm is ((SR & 0xFFFFFF0F) | V)
with its own V (Power Stone FUN_0c10b7b0: r9 on one path, another value on the other). The join left r0 unreadable ("dirty r0") and the
function was skipped; the arms' V values go into one variable, and set_imask takes it. No game data, no compiler: a synthetic
executable of one small function. Stdlib only.

    imask_join    mov.w @pool,r2 ; tst r4,r4 ; bt ELSE
                  THEN: stc sr,r1 ; mov r5,r0 ; and #15,r0 ; shll2 r0 ; shll2 r0 ; and r2,r1 ; or r1,r0 ; bra JOIN ; nop
                  ELSE: stc sr,r1 ; mov r6,r0 ; and #15,r0 ; shll2 r0 ; shll2 r0 ; and r2,r1 ; or r1,r0
                  JOIN: ldc r0,sr ; rts ; nop ; pool: 0xFF0F
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
TOOLS = os.path.join(SKILL, 'scripts', 'tools')
BASE = 0x8C010000

CODE = [0x9214,                       # 0  mov.w @(pool),r2        (pool at word 22: 0xFF0F, sign-extended 0xFFFFFF0F)
        0x2448,                       # 1  tst r4,r4
        0x8908,                       # 2  bt ELSE (word 12)
        0x0102, 0x6053, 0xC90F, 0x4008, 0x4008, 0x2129, 0x201B,      # 3-9   THEN: stc sr,r1 / mov r5,r0 / and #15,r0 / shll2 x2 / and r2,r1 / or r1,r0
        0xA007, 0x0009,               # 10-11 bra JOIN (word 19) / nop
        0x0102, 0x6063, 0xC90F, 0x4008, 0x4008, 0x2129, 0x201B,      # 12-18 ELSE: the same with r6
        0x400E, 0x000B, 0x0009,       # 19-21 JOIN: ldc r0,sr / rts / nop
        0xFF0F]                       # 22 pool


class TestSrJoin(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        data = b''.join(struct.pack('<H', w) for w in CODE)
        open(os.path.join(cls.tmp.name, '1ST_READ.BIN'), 'wb').write(data + b'\x09\x00')
        open(os.path.join(cls.tmp.name, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(cls.tmp.name, 'functions.txt'), 'w').write('F %08x %d imask_join\n' % (BASE, len(data) + 2))
        for d in ('src', 'tests', 'build'):
            os.makedirs(os.path.join(cls.tmp.name, d))
        shutil.copytree(TOOLS, os.path.join(cls.tmp.name, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        script = ("import sys; sys.path[:0] = ['tools', 'tools/5-generated/gen_equiv']; import toolpath, gen_core, gen_drv\n"
                  "try:\n"
                  "    s, c = gen_drv.build('imask_join', 'void', False); print('WRITTEN'); print(s)\n"
                  "except Exception as e: print('SKIPPED', type(e).__name__, e)\n")
        r = subprocess.run([sys.executable, '-B', '-c', script], cwd=cls.tmp.name, capture_output=True, text=True)
        cls.out = r.stdout + r.stderr

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_arms_with_different_masks_are_written(self):
        self.assertIn('WRITTEN', self.out.splitlines()[0], self.out)

    def test_the_mask_is_set_once_from_the_merged_value(self):
        self.assertEqual(self.out.count('_builtin_set_imask('), 1, self.out)

    def test_both_arguments_reach_the_mask(self):
        self.assertIn('a5', self.out, self.out)
        self.assertIn('a6', self.out, self.out)


if __name__ == '__main__':
    unittest.main()
