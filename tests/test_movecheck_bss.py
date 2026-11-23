#!/usr/bin/env python3
"""Where the padded image's BSS lands (scripts/tools/1-2-baseline/movecheck.py bss_shift() and mapper(bss_align=)). No game data, no
compiler, no simulator. Stdlib only.

The padded link moves BSS up by all the pads. The game's code rounds addresses: `and #-256` then `add #256` on a pointer into BSS
(Power Stone 2 0C02D2DE: 0C31F19C becomes 0C31F200) rounds up to the next 256. Round-up is not the same as shift-then-round when the
shift is not a multiple of the alignment: the shift was 0x172C0, so the padded image stored 0C336500 where the shifted original value
was 0C3364C0, and check 2 reported DIFFERS on a program that behaves the same. A BSS shift that is a multiple of 0x1000 (more than any
alignment the games use) keeps every round-up the same, and the BSS addresses still map by one number.

    check.py      round     the shift is the pads rounded up to a multiple of the alignment; a multiple stays; 0 means as it was
                  default   mapper() without bss_align moves BSS by all the pads, as before
                  mapper    with bss_align, an address in BSS moves by bss_shift(); one below the end does not
                  align     a pointer rounded up to 256 in the original maps to the same pointer rounded up in the padded image
                            (with the old shift it does not, on these numbers)
"""
import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools', '1-2-baseline'))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools'))
import movecheck  # noqa: E402

END = 0x0C304399
LO = 0x0C010000
GSTART = [LO + 0x100 * k for k in range(2967)]        # 2967 groups: 2966 pads of 32 bytes = 0x172C0
ROUND = lambda x, a: (x + a - 1) // a * a


class TestBss(unittest.TestCase):
    def test_round(self):
        self.assertEqual(movecheck.bss_shift(32, 2967, 0x1000), 0x18000)          # 0x172C0 up to a multiple of 0x1000
        self.assertEqual(movecheck.bss_shift(32, 129, 0x1000), 0x1000)            # 4096 exactly: it stays
        self.assertEqual(movecheck.bss_shift(32, 2967, 0), 0x172C0)               # 0: as it was
        self.assertEqual(movecheck.bss_shift(32, 1, 0x1000), 0)                   # one group: no pad, no shift

    def test_default(self):
        new = movecheck.mapper(GSTART, 32, END, LO, 0x0C400000)
        self.assertEqual(new(0x0C31F200), 0x0C31F200 + 0x172C0)

    def test_mapper(self):
        new = movecheck.mapper(GSTART, 32, END, LO, 0x0C900000, bss_align=0x1000)
        self.assertEqual(new(0x0C31F200), 0x0C31F200 + 0x18000)
        self.assertEqual(new(0x8C31F200), 0x8C31F200 + 0x18000)                   # a mirror too
        self.assertEqual(new(LO), LO)                                             # the first group does not move
        self.assertEqual(new(LO + 0x250), LO + 0x250 + 32 * 2)                    # below the end: by the groups before it, as before

    def test_align(self):
        new_old = movecheck.mapper(GSTART, 32, END, LO, 0x0C900000)
        new = movecheck.mapper(GSTART, 32, END, LO, 0x0C900000, bss_align=0x1000)
        x = 0x0C31F19C
        self.assertNotEqual(ROUND(new_old(x), 0x100), new_old(ROUND(x, 0x100)))   # the report: 0C336500 against 0C3364C0
        rng = random.Random(5)
        for _ in range(500):
            x = rng.randrange(0x0C304400, 0x0C8E0000)
            for a in (0x10, 0x20, 0x100, 0x400, 0x1000):
                self.assertEqual(ROUND(new(x), a), new(ROUND(x, a)), '%08X rounded to %X' % (x, a))


if __name__ == '__main__':
    unittest.main()
