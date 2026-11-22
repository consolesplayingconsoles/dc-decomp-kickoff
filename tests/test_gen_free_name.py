#!/usr/bin/env python3
"""The generator names a new file with a name no file has, in any folder (scripts/tools/5-generated/gen_equiv/__main__.py).
No game data, no compiler. Stdlib only.

    anywhere   the name is checked against every C file of the repo (tools/common/layout.py), not against src/ alone: with the
               SDK's C in sdk/<library>/, `gen_g` was free in src/ and taken in sdk/naomi/, the new file was written through
               the name lookup, and it replaced sdk/naomi/gen_g.c and its function (Crazy Taxi, nlObjPutSetLightDirectionV)
    cases      a name whose cases folder exists is not free either
"""
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(os.path.dirname(HERE), 'scripts', 'tools', '5-generated', 'gen_equiv', '__main__.py')


class GenFreeName(unittest.TestCase):
    def setUp(self):
        with open(MAIN) as fp:
            self.text = fp.read()

    def test_anywhere(self):
        self.assertNotIn("os.path.exists('src/gen_%s.c'%x)", self.text)
        self.assertIn("'gen_'+x not in _taken()", self.text)
        self.assertIn('layout.stem(f) for f in layout.c_files()', self.text)

    def test_cases(self):
        self.assertIn("os.listdir('tests')", self.text[self.text.index('def _taken'):self.text.index('def _taken') + 400])


if __name__ == '__main__':
    unittest.main()
