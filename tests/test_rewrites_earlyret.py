"""Returns written where the result is known (scripts/tools/5-generated/gen_equiv/rewrites.py early_returns). No game data, no
compiler. Stdlib only.

The structured form carries a function's result in one temporary to a single `return` at the end, assigning it at the end of each
arm of its nested ifs. The compiler keeps the temporary alive through the nest (in one library function the parameter went to the
frame and was reloaded 15 times); the source it came from returns at each test. An assignment to the returned temporary that is the
last statement of an arm, with nothing between the end of that if and the `return`, is that `return`.

    early_returns   tail      `tR = E;` as the last statement of an if arm right before `return tR;` becomes `return E;`
                    nested    the same through nested ifs and else arms, each arm on its own
                    else-if   an `} else if (...) {` arm counts as an arm
                    kept      the assignment before the if stays (the path that skips the arm still returns it)
                    middle    an assignment that is not the last statement of its arm is left as it is
                    after     a statement, a label or a call between the if and the return: nothing changes
                    loop      an if inside a loop is not in tail position: nothing changes
                    type      a temporary whose type is not the function's return type is left as it is
                    void      a function that returns nothing is left as it is
                    again     a second run changes nothing
"""
import os
import sys
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'tools')


def fn(body, ret='int', decl='    register int t1;\n    register int t2;\n'):
    return '%s f(int a4)\n{\n%s%s}\n' % (ret, decl, body)


class TestEarlyReturns(unittest.TestCase):
    def setUp(self):
        saved = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved)
        sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import rewrites
        self.er = rewrites.early_returns

    def test_tail(self):
        src = fn('    t1 = (-1);\n    if (a4 != 0) {\n        t2 = g(a4);\n        t1 = (t2 + 0x1);\n    }\n    return t1;\n')
        got = self.er(src)
        self.assertIn('        return (t2 + 0x1);\n', got)
        self.assertNotIn('        t1 = (t2 + 0x1);', got)

    def test_kept(self):
        got = self.er(fn('    t1 = (-1);\n    if (a4 != 0) {\n        t1 = (0x2);\n    }\n    return t1;\n'))
        self.assertIn('    t1 = (-1);\n', got)
        self.assertIn('    return t1;\n}\n', got)

    def test_nested(self):
        src = fn('    t1 = (-1);\n    if (a4 != 0) {\n        t2 = g(a4);\n        if (t2 == 0) {\n            t1 = (0x5);\n'
                 '        } else {\n            h();\n            t1 = (t2);\n        }\n    } else {\n        t1 = (0x7);\n    }\n    return t1;\n')
        got = self.er(src)
        for want in ('            return (0x5);\n', '            return (t2);\n', '        return (0x7);\n'):
            self.assertIn(want, got)
        self.assertNotIn('t1 = (0x5)', got)

    def test_else_if(self):
        src = fn('    t1 = (0x0);\n    if (a4 == 1) {\n        t1 = (0x3);\n    } else if (a4 == 2) {\n        t1 = (0x4);\n    }\n    return t1;\n')
        got = self.er(src)
        self.assertIn('        return (0x3);\n', got)
        self.assertIn('        return (0x4);\n', got)

    def test_middle(self):
        src = fn('    t1 = (-1);\n    if (a4 != 0) {\n        t1 = (0x2);\n        h();\n    }\n    return t1;\n')
        self.assertEqual(self.er(src), src)

    def test_after(self):
        for mid in ('    h();\n', 'L1:;\n', '    t2 = (0x1);\n'):
            src = fn('    t1 = (-1);\n    if (a4 != 0) {\n        t1 = (0x2);\n    }\n' + mid + '    return t1;\n')
            self.assertEqual(self.er(src), src)

    def test_loop(self):
        src = fn('    t1 = (-1);\n    for (;;) {\n        if (a4 != 0) {\n            t1 = (0x2);\n        }\n        break;\n    }\n    return t1;\n')
        self.assertEqual(self.er(src), src)
        src = fn('    t1 = (-1);\n    for (;;) {\n        t1 = (0x2);\n    }\n    return t1;\n')
        self.assertEqual(self.er(src), src)

    def test_type(self):
        src = fn('    t1 = (-1);\n    if (a4 != 0) {\n        t1 = (0x2);\n    }\n    return t1;\n', decl='    register unsigned short t1;\n')
        self.assertEqual(self.er(src), src)
        src = fn('    t1 = (1.0f);\n    if (a4 != 0) {\n        t1 = (2.0f);\n    }\n    return t1;\n', ret='float', decl='    float t1;\n')
        self.assertIn('        return (2.0f);\n', self.er(src))

    def test_void(self):
        src = fn('    if (a4 != 0) {\n        t1 = (0x2);\n    }\n    return;\n', ret='void')
        self.assertEqual(self.er(src), src)

    def test_again(self):
        once = self.er(fn('    t1 = (-1);\n    if (a4 != 0) {\n        t1 = (0x2);\n    }\n    return t1;\n'))
        self.assertEqual(self.er(once), once)

    def test_two_functions(self):
        a = fn('    t1 = (-1);\n    if (a4 != 0) {\n        t1 = (0x2);\n    }\n    return t1;\n')
        got = self.er(a + '\n' + a.replace(' f(', ' g2('))
        self.assertEqual(got.count('        return (0x2);\n'), 2)


if __name__ == '__main__':
    unittest.main()
