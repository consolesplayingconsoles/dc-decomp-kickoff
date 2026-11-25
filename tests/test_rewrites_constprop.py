"""A constant held in a temporary is read straight in the statements that follow (rewrites.py const_prop; shrink.py --passes constprop).
No game data, no compiler. Stdlib only.

    const_prop  uses      `t1 = 0x10;` and the next statements that read t1 read 0x10, up to a new value of t1
                brace     the run ends at a brace, a label or a goto
                inplace   `t1 += 1;` and a name whose address is taken are left
                other     a temporary assigned an expression is left
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
        self.p = getattr(rewrites, 'const_prop')

    def test_uses(self):
        got = self.p(fn('    t1 = 0x10;\n    t2 = (a4 + t1);\n    t2 = (t2 + t1);\n    t1 = (t1 + 0x1);\n    t3 = t1;\n    return t2;\n', '    int t1;\n    int t2;\n    int t3;\n'))
        self.assertIn('t2 = (a4 + 0x10);', got)
        self.assertIn('t2 = (t2 + 0x10);', got)
        self.assertIn('t1 = (0x10 + 0x1);', got)
        self.assertIn('t3 = t1;', got)

    def test_brace(self):
        src = fn('    t1 = 0x10;\n    if (a4) {\n        t2 = t1;\n    }\n    return t2;\n', '    int t1;\n    int t2;\n')
        self.assertEqual(self.p(src), src)
        src = fn('    t1 = 0x10;\n    L_1:;\n    t2 = t1;\n    return t2;\n', '    int t1;\n    int t2;\n')
        self.assertEqual(self.p(src), src)

    def test_inplace(self):
        src = fn('    t1 = 0x10;\n    t1 += 1;\n    t2 = t1;\n    return t2;\n', '    int t1;\n    int t2;\n')
        self.assertEqual(self.p(src), src)
        src = fn('    t1 = 0x10;\n    g(&t1);\n    t2 = t1;\n    return t2;\n', '    int t1;\n    int t2;\n')
        self.assertEqual(self.p(src), src)

    def test_other(self):
        src = fn('    t1 = (a4 + 0x10);\n    t2 = t1;\n    return t2;\n', '    int t1;\n    int t2;\n')
        self.assertEqual(self.p(src), src)

    def test_again(self):
        once = self.p(fn('    t1 = 0x10;\n    t2 = (a4 + t1);\n    return t2;\n', '    int t1;\n    int t2;\n'))
        self.assertEqual(self.p(once), once)

if __name__ == '__main__':
    unittest.main()
