"""Constant offset arithmetic written in two steps is written in one (rewrites.py fold_offsets; shrink.py --passes fold).
No game data, no compiler. Stdlib only.

    fold_offsets  sum      `((a4 + 0x10) - 0x4)` becomes `(a4 + 0xC)`
                  zero     `(a4 + 0x0)` becomes `a4`
                  double   `((a4 + 0x4))` becomes `(a4 + 0x4)`
                  other    a product, a sum of two variables and a lone offset are left
                  again    a second run changes nothing
"""
import os
import sys
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'tools')


def fn(body, decls='', head='int f(int a4)'):
    return head + '\n{\n' + decls + '\n' + body + '}\n'


class Test(unittest.TestCase):
    def setUp(self):
        saved = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved)
        sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import rewrites
        self.rw = rewrites
        self.p = getattr(rewrites, 'fold_offsets')

    def test_sum(self):
        self.assertEqual(self.p('x = ((a4 + 0x10) - 0x4);'), 'x = (a4 + 0xC);')
        self.assertEqual(self.p('x = ((a4 - 0x10) + 0x4);'), 'x = (a4 - 0xC);')

    def test_zero(self):
        self.assertEqual(self.p('x = (a4 + 0x0);'), 'x = a4;')
        self.assertEqual(self.p('x = ((a4 + 0x4) - 0x4);'), 'x = a4;')

    def test_double(self):
        self.assertEqual(self.p('x = *(int *)((a4 + 0x4));'), 'x = *(int *)(a4 + 0x4);')

    def test_other(self):
        for s in ('x = ((a4 + 0x10) * 0x4);', 'x = ((a4 + t1) - 0x4);', 'x = (a4 + 0x10);', 'x = (((int)a4 + 0x10) - 0x4);'):
            self.assertEqual(self.p(s), s)

    def test_again(self):
        once = self.p('x = (((a4 + 0x10) - 0x4) + 0x8);')
        self.assertEqual(self.p(once), once)

if __name__ == '__main__':
    unittest.main()
