#!/usr/bin/env python3
"""A function that ends by branching into the middle of another function, into a tail longer than an epilogue
(scripts/tools/5-generated/gen_equiv/gen_core.py tail_region; sh4sim.shared_epilogue takes only pops and a return). Power Stone
FUN_0c0fd240 -> 0C0FC870, the rest of FUN_0c0fc812; FUN_0c0f22d0 and FUN_0c0fa966, whose tails branch back to earlier code of the
other function. The generator skipped the caller ("branch past the listed size"); the code control flow reaches from the target, down
to the code its branches go back to, is now the caller's own ending. No game data, no compiler: a synthetic executable. Stdlib only.

    caller    mov #3,r0 ; bra TAIL ; nop                                   enters the tail of host
    host      0: mov #1,r0 ; rts ; nop            8: BACK: mov #9,r0 ; rts ; nop
              16: TAIL: add #5,r0 ; tst r0,r0 ; bt BACK ; rts ; nop       the tail branches back to BACK, below it
    plain     mov #3,r0 ; rts ; nop                                       a function with no such branch, unchanged
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
HOST = BASE + 0x40
TAIL = HOST + 0x10
BACK = HOST + 0x08


def bra(at, to):
    return 0xA000 | (((to - (at + 4)) >> 1) & 0xFFF)


def bt(at, to):
    return 0x8900 | (((to - (at + 4)) >> 1) & 0xFF)


def image():
    caller = [0xE003, bra(BASE + 2, TAIL), 0x0009]
    plain = [0xE003, 0x000B, 0x0009]
    host = [0xE001, 0x000B, 0x0009, 0x0009,                 # 0:  mov #1,r0 / rts / nop / pad
            0xE009, 0x000B, 0x0009, 0x0009,                 # 8:  BACK: mov #9,r0 / rts / nop / pad
            0x7005, 0x2008, bt(HOST + 0x14, BACK), 0x000B, 0x0009]    # 16: TAIL: add #5,r0 / tst r0,r0 / bt BACK / rts / nop
    gapcaller = [0xE003, bra(BASE + 0x62, BASE + 0xA0), 0x0009]
    gaptail = [0x7005, 0x000B, 0x0009]                           # a tail in code no entry owns, past other functions
    img = bytearray(b'\x09\x00' * 0xE0)
    for off, words in ((0, caller), (0x20, plain), (0x40, host), (0x60, gapcaller), (0xA0, gaptail)):
        for i, w in enumerate(words):
            struct.pack_into('<H', img, off + 2 * i, w)
    return bytes(img)


class TestTailRegion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        open(os.path.join(cls.tmp.name, '1ST_READ.BIN'), 'wb').write(image())
        open(os.path.join(cls.tmp.name, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(cls.tmp.name, 'functions.txt'), 'w').write(
            'F %08x 6 caller\nF %08x 6 plain\nF %08x 26 host\nF %08x 6 gapcaller\nF %08x 6 mid\nF %08x 6 after\n' % (BASE, BASE + 0x20, HOST, BASE + 0x60, BASE + 0x80, BASE + 0xC0))
        for d in ('src', 'tests', 'build'):
            os.makedirs(os.path.join(cls.tmp.name, d))
        shutil.copytree(TOOLS, os.path.join(cls.tmp.name, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        script = ("import sys; sys.path[:0] = ['tools', 'tools/5-generated/gen_equiv']; import toolpath, gen_core, gen_drv\n"
                  "for n in ('caller', 'plain', 'gapcaller'):\n"
                  "    try:\n"
                  "        s, c = gen_drv.build(n, 'r0', False); print('@@@@', n, 'WRITTEN'); print(s)\n"
                  "    except Exception as e: print('@@@@', n, 'SKIPPED', type(e).__name__, e)\n")
        r = subprocess.run([sys.executable, '-B', '-c', script], cwd=cls.tmp.name, capture_output=True, text=True)
        cls.out = r.stdout + r.stderr
        cls.parts = {}
        for chunk in cls.out.split('@@@@ ')[1:]:
            head, _, text = chunk.partition('\n')
            cls.parts[head.split()[0]] = (head, text)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_a_tail_longer_than_an_epilogue_is_the_functions_own_ending(self):
        head = self.parts.get('caller', ('', ''))[0]
        self.assertIn('WRITTEN', head, self.out)

    def test_the_value_the_tail_computes_is_returned(self):
        text = self.parts.get('caller', ('', ''))[1]
        self.assertRegex(text, r'return [^;]*(0x8|\b8\b|\(.*\+ 0x5\))', self.out)

    def test_a_tail_in_an_unlisted_gap_past_other_functions_is_followed(self):
        self.assertIn('WRITTEN', self.parts.get('gapcaller', ('', ''))[0], self.out)

    def test_a_function_without_such_a_branch_is_unchanged(self):
        self.assertIn('WRITTEN', self.parts.get('plain', ('', ''))[0], self.out)


if __name__ == '__main__':
    unittest.main()
