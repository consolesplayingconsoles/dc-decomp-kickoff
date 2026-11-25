"""splice keeps a comment above the first definition attached to it (scripts/tools/5-generated/gen_equiv/rewrites.py splice). No game
data, no compiler. Stdlib only.

splice declares the one-field structures a rewritten function names after the unit's head, before its first definition. When that
first definition carried a `/* manual: */` line right above it, the declarations went between the two, and the function no longer
counted as written by hand (consistency.manual_names reads the comment right above a definition): three hand versions lost their
mark in one shrink run.

    splice   marker    the comment right above the first definition stays right above it; the declarations go before the comment
             plain     with no comment there, the declarations go right before the first definition, as before
"""
import os
import sys
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'tools')

UNIT = ('int g(int);\n\n/* manual: written by hand */\nvoid f(int a4)\n{\n    g(a4);\n}\n\n'
        'int h(int a4)\n{\n    return *(unsigned int *)(a4 + 0xC);\n}\n')
NEW_H = 'int h(int a4)\n{\n    return (((struct oC_uint *)(a4))->v);\n}\n'


class TestSpliceMarker(unittest.TestCase):
    def setUp(self):
        saved = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved)
        sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import rewrites
        self.splice = rewrites.splice

    def test_marker(self):
        got = self.splice(UNIT, {'h': NEW_H})
        self.assertIn('/* manual: written by hand */\nvoid f(int a4)\n', got)
        self.assertLess(got.index('struct oC_uint'), got.index('/* manual:'))

    def test_plain(self):
        unit = UNIT.replace('/* manual: written by hand */\n', '')
        got = self.splice(unit, {'h': NEW_H})
        self.assertLess(got.index('struct oC_uint'), got.index('void f(int a4)'))
        self.assertLess(got.index('int g(int);'), got.index('struct oC_uint'))


if __name__ == '__main__':
    unittest.main()
