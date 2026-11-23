#!/usr/bin/env python3
"""classify.entry_input (scripts/tools/5-generated/classify.py): does a function read r0-r3 before writing it. No game data. Stdlib only.

`exts.w r0,r0` (and the other one-register converts, `extu.b r1,r1`) writes its LAST operand and reads its FIRST: with the same register in both
places the register is read. Skipping every operand equal to the destination hid that read, so a function taking its value in r0 was not
listed as having an input there.

    check.py      sameregister  exts.w r0,r0 at the entry:                    r0 is read          -> True
                  written       mov r5,r0 then exts.w r0,r0:                 r0 was written      -> False
                  source        exts.w r0,r1 at the entry:                   r0 is read          -> True
                  plain         mov r5,r0 ; rts ; nop:                       nothing read        -> False
"""
import os
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools', '5-generated'))
import classify  # noqa: E402

BASE = 0x0C010000
EXTSW = lambda n, m: 0x600F | (n << 8) | (m << 4)   # exts.w Rm,Rn
MOV = lambda n, m: 0x6003 | (n << 8) | (m << 4)     # mov Rm,Rn
NOP, RTS = 0x0009, 0x000B


def run(*ws):
    exe = b''.join(struct.pack('<H', w) for w in ws)
    return classify.entry_input(exe, BASE, BASE, len(exe))


class TestEntryInput(unittest.TestCase):
    def test_sameregister(self):
        self.assertTrue(run(EXTSW(0, 0), RTS, NOP), 'exts.w r0,r0 reads r0')

    def test_written(self):
        self.assertFalse(run(MOV(0, 5), EXTSW(0, 0), RTS, NOP), 'r0 was written first')

    def test_source(self):
        self.assertTrue(run(EXTSW(1, 0), RTS, NOP), 'exts.w r0,r1 reads r0')

    def test_plain(self):
        self.assertFalse(run(MOV(0, 5), RTS, NOP))


if __name__ == '__main__':
    unittest.main()
