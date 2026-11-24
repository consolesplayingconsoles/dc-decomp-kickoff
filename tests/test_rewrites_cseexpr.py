"""A pure expression written at two places or more becomes one local (rewrites.py cse_expr; shrink.py --passes cseexpr). Failures found on real functions: `if qe0 goto L;` without parentheses, an int local holding a function pointer that was then called ("Illegal function call"), a call s argument list taken as an expression, and one function that always DIFFERED (a local set where its statement did not dominate every use).
No game data, no compiler. Stdlib only.

    cse_expr  local     `((t1 + t2) * 0x1234)` at two uses: `qe0 = ...;` before the first, `register int qe0;`
              cond      FUN_0c14b012: a condition's own parentheses stay: `if (qe0) goto L;`
              fnptr     FUN_0c0d1ec4: a cast function name `((int (*)(int, int))(FUN_0c03f346))` is never held in a local
              args      FUN_0c142bdc: a call's argument list `((v0_0 + 0x28), w0_0, w0_0)` is not an expression
              callargs  `g((t1 + t2) * ...)` style: the argument parentheses of a call are never replaced by a name
              arm       a use in each arm of an if/else (the statement does not dominate both) leaves it
              label     a label between the first and the last use leaves it
              operand   an operand assigned after the first use leaves it
              address   an operand whose address is taken leaves it
              float     a float expression is a float local, a comparison an int local
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
        self.p = getattr(rewrites, 'cse_expr')

    D = '    int t1;\n    int t2;\n    int t3;\n    int t4;\n'
    E = '(((t1 + t2) * 0x1234) - (t3 << 0x2))'

    def test_local(self):
        got = self.p(fn('    t4 = (' + self.E + ' + 0x1);\n    a4 = (' + self.E + ' + 0x2);\n    return t4;\n', self.D))
        self.assertIn('    qe0 = ' + self.E + ';\n', got)
        self.assertEqual(got.count(self.E), 1)
        self.assertIn('register int qe0;', got)

    def test_cond(self):
        e = '(((int)(short)(t1 - 0x1) > 0x0) + t2)'
        got = self.p(fn('    if (' + e + ') goto L_1;\n    t3 = 0;\n    L_1:;\n    return 0;\n    if (' + e + ') goto L_1;\n', self.D))
        self.assertNotIn('if qe0', got)
        self.assertEqual(got, got)

    def test_cond_whole(self):
        e = '(((int)(short)(t1 - 0x1) > 0x0))'
        got = self.p(fn('    if ' + e + ' goto L_1;\n    t3 = ' + e + ';\n    t2 = ' + e + ';\n    L_1:;\n    return 0;\n', self.D).replace('if ' + e + ' goto', 'if (' + e[1:-1] + ') goto') + '')
        for l in got.split('\n'):
            self.assertEqual(l.count('('), l.count(')'), l)
            self.assertNotRegex(l, r'if qe')

    def test_cond_label_dominates(self):
        # FUN_0c14b012: the same condition after a label is not covered by a statement before the first (label between)
        e = '((int)(short)(t1 - 0x1) > 0x0)'
        src = fn('    if (' + e + ') goto L_1;\n    L_2:;\n    if (' + e + ') goto L_1;\n    L_1:;\n    return 0;\n', self.D)
        self.assertEqual(self.p(src), src)

    def test_fnptr(self):
        f = '((int (*)(int, int, int, int))(FUN_0c03f346))'
        src = fn('    t1 = ' + f + '(a4, t2, t3, t3);\n    t2 = ' + f + '(a4, t2, t3, t3);\n', self.D)
        self.assertEqual(self.p(src), src)

    def test_args(self):
        src = fn('    g((a4 + 0x28), t1, t1, t1, t1);\n    h((a4 + 0x28), t1, t1, t1, t1);\n', self.D)
        self.assertEqual(self.p(src), src)

    def test_callargs(self):
        e = '(((t1 + t2) * 0x1234) - (t3 << 0x2))'
        src = fn('    g' + e + ';\n    h' + e + ';\n', self.D)
        self.assertEqual(self.p(src), src)

    def test_arm(self):
        src = fn('    if (t1) {\n        t2 = (' + self.E + ' + 0x1);\n    } else {\n        t2 = (' + self.E + ' + 0x2);\n    }\n    return t2;\n', self.D)
        got = self.p(src)
        self.assertEqual(got, src)

    def test_label(self):
        src = fn('    t2 = (' + self.E + ' + 0x1);\n    L_1:;\n    t3 = (' + self.E + ' + 0x2);\n    return t3;\n', self.D)
        self.assertEqual(self.p(src), src)

    def test_operand(self):
        src = fn('    t2 = (' + self.E + ' + 0x1);\n    t1 = 5;\n    t3 = (' + self.E + ' + 0x2);\n    return t3;\n', self.D)
        self.assertEqual(self.p(src), src)

    def test_address(self):
        src = fn('    g(&t1);\n    t2 = (' + self.E + ' + 0x1);\n    t3 = (' + self.E + ' + 0x2);\n    return t3;\n', self.D)
        self.assertEqual(self.p(src), src)

    def test_float(self):
        e = '(((float)t1 * 2.0f) + ((float)t2 * 3.0f))'
        got = self.p(fn('    u1 = (' + e + ' * 1.0f);\n    u2 = (' + e + ' * 2.0f);\n    return 0;\n', self.D + '    float u1;\n    float u2;\n'))
        self.assertIn('register float qe0;', got)

    def test_again(self):
        once = self.p(fn('    t4 = (' + self.E + ' + 0x1);\n    a4 = (' + self.E + ' + 0x2);\n    return t4;\n', self.D))
        self.assertEqual(self.p(once), once)

if __name__ == '__main__':
    unittest.main()
