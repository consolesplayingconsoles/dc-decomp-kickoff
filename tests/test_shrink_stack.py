"""--stack: several passes as one rewrite (scripts/tools/5-generated/gen_equiv/rewrites.py compose_passes, scripts/tools/7-reduction/
shrink.py). No game data, no compiler. Stdlib only.

shrink.py --passes keeps each pass only when it alone makes a function smaller, so a pass that pays only after another (the member
form once the register declarations are gone) never survives. --stack applies the list in order as one rewrite, measured and proven
once.

    compose_passes   order     the passes run in the order given, each on what the one before gave
                     empty     no pass: the text as it is
    shrink.py        wired     --stack makes PASSES one `stack:a+b+c` entry, looked up through pass_function; narrow is refused
"""
import os
import sys
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'tools')


class TestStack(unittest.TestCase):
    def setUp(self):
        saved = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved)
        sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import rewrites
        self.rw = rewrites

    def test_order(self):
        run = self.rw.compose_passes([lambda t: t + 'a', lambda t: t.replace('a', 'b'), lambda t: t + 'c'])
        self.assertEqual(run('x'), 'xbc')

    def test_empty(self):
        self.assertEqual(self.rw.compose_passes([])('x'), 'x')

    def test_wired(self):
        src = open(os.path.join(TOOLS, '7-reduction', 'shrink.py')).read()
        self.assertIn("if '--stack' in args:", src)
        self.assertIn("PASSES = ['stack:' + '+'.join(PASSES)]", src)
        self.assertIn('def pass_function(pas):', src)
        self.assertIn('fn_ = pass_function(pas)', src)
        self.assertIn("'narrow' in PASSES", src)


if __name__ == '__main__':
    unittest.main()
