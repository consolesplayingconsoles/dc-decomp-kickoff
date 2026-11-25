"""A product written at three places or more is computed once (rewrites.py mul_once; shrink.py --passes mulonce).
No game data, no compiler. Stdlib only.

    mul_once  once      `(t5 * 0x38)` at three places, t5 assigned once: a `qm0 = (t5 * 0x38);` after the assignment, the uses read it
              two       two uses are left
              twice     a temporary assigned twice is left
              before    a use before the assignment is left
              address   a temporary whose address is taken is left
              again     a second run changes nothing
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
        self.p = getattr(rewrites, 'mul_once')

    D = '    int t5;\n    int t6;\n'
    USES = '    t6 = (t5 * 0x38);\n    t6 = (t6 + (t5 * 0x38));\n    t6 = (t6 + (t5 * 0x38));\n    return t6;\n'

    def test_once(self):
        got = self.p(fn('    t5 = a4;\n' + self.USES, self.D))
        self.assertIn('    t5 = a4;\n    qm0 = (t5 * 0x38);\n', got)
        self.assertEqual(got.count('(t5 * 0x38)'), 1)
        self.assertIn('register int qm0;', got)

    def test_two(self):
        src = fn('    t5 = a4;\n    t6 = (t5 * 0x38);\n    t6 = (t6 + (t5 * 0x38));\n    return t6;\n', self.D)
        self.assertEqual(self.p(src), src)

    def test_twice(self):
        src = fn('    t5 = a4;\n    t5 = 1;\n' + self.USES, self.D)
        self.assertEqual(self.p(src), src)

    def test_before(self):
        src = fn('    t6 = (t5 * 0x38);\n    t5 = a4;\n    t6 = (t6 + (t5 * 0x38));\n    t6 = (t6 + (t5 * 0x38));\n    return t6;\n', self.D)
        self.assertEqual(self.p(src), src)

    def test_address(self):
        src = fn('    t5 = a4;\n    g(&t5);\n' + self.USES, self.D)
        self.assertEqual(self.p(src), src)

    def test_again(self):
        once = self.p(fn('    t5 = a4;\n' + self.USES, self.D))
        self.assertEqual(self.p(once), once)

if __name__ == '__main__':
    unittest.main()
