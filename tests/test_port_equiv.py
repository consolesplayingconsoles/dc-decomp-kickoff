#!/usr/bin/env python3
"""The C a port carries from one decomp to another names the destination's addresses (scripts/tools/4-boosts/port_equiv.py).
No game data, no compiler. Stdlib only.

    literal    a function whose C holds the source's address as a number (`v0_5 = (0x8C46ABA4);`, an ADX work area in
               Virtua Tennis) is carried with the destination's address for it (`0x0C2F4C9C` in Crazy Taxi), the one the
               literal pools of the matched pair give: the cases were translated, the C was not, and the function failed
               its check in the destination although its code is the same
    unmapped   an address the pools do not map stays as it is (the check decides)
    small      a small number that happens to be a key's low digits is not an address: `0x3C` stays
    twice      every occurrence is translated, in upper or lower case
    cast       an address inside a cast expression, `*(int *)0x8C46ABA4`, is translated too
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(SKILL, 'scripts', 'tools', '4-boosts'))
sys.path.insert(0, os.path.join(SKILL, 'scripts', 'tools'))
import port_equiv  # noqa: E402

AMAP = {0x8C46ABA4: 0x0C2F4C9C, 0x8C1F0F2C: 0x0C168DE8}


class TranslateC(unittest.TestCase):
    def test_literal(self):
        out = port_equiv.translate_c('    v0_5 = (0x8C46ABA4);\n', AMAP)
        self.assertEqual(out, '    v0_5 = (0x0C2F4C9C);\n')

    def test_unmapped(self):
        text = '    t1 = *(int *)0x8C300010;\n'
        self.assertEqual(port_equiv.translate_c(text, AMAP), text)

    def test_small(self):
        text = '    t2 = t1 + 0x3C; t3 = 0xABA4;\n'
        self.assertEqual(port_equiv.translate_c(text, AMAP), text)

    def test_twice(self):
        out = port_equiv.translate_c('a = 0x8c46aba4; b = 0x8C46ABA4; f = ((int (*)(void))(0x8C1F0F2C))();', AMAP)
        self.assertEqual(out, 'a = 0x0C2F4C9C; b = 0x0C2F4C9C; f = ((int (*)(void))(0x0C168DE8))();')

    def test_cast(self):
        out = port_equiv.translate_c('    t0 = *(int *)0x8C46ABA4;\n', AMAP)
        self.assertEqual(out, '    t0 = *(int *)0x0C2F4C9C;\n')


if __name__ == '__main__':
    unittest.main()
