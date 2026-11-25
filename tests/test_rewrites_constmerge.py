"""A temporary whose every assignment is one literal is replaced by the literal (rewrites.py merge_constants; shrink.py --passes constmerge).
No game data, no compiler. Stdlib only.

    merge_constants  int       `t5 = 0x4;` in two arms and nowhere else: t5 is 0x4 everywhere, assignments and declaration gone
                     float     a float temporary takes a float literal
                     kind      an int temporary assigned a float literal, a float one an int literal, are left (the arithmetic would change)
                     values    two different values are left
                     other     a name changed in place or with its address taken is left; a name assigned from an expression is left
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
        self.p = getattr(rewrites, 'merge_constants')

    def test_int(self):
        got = self.p(fn('    if (a4) {\n        t5 = 0x4;\n    } else {\n        t5 = 0x4;\n    }\n    return (t5 + a4);\n', '    int t5;\n'))
        self.assertIn('return (0x4 + a4);', got)
        self.assertNotIn('t5', got)

    def test_float(self):
        got = self.p(fn('    u5 = 2.0f;\n    return (int)(u5 * u5);\n', '    float u5;\n'))
        self.assertIn('(int)(2.0f * 2.0f)', got)

    def test_kind(self):
        for d, v in (('int t5;', '1.5f'), ('float u5;', '0x10')):
            n = 't5' if d[0] == 'i' else 'u5'
            src = fn('    %s = %s;\n    return (int)(%s + a4);\n' % (n, v, n), '    %s\n' % d)
            self.assertEqual(self.p(src), src)

    def test_values(self):
        src = fn('    if (a4) {\n        t5 = 0x4;\n    } else {\n        t5 = 0x8;\n    }\n    return t5;\n', '    int t5;\n')
        self.assertEqual(self.p(src), src)

    def test_other(self):
        for body in ('    t5 = 0x4;\n    t5 += 1;\n    return t5;\n', '    t5 = 0x4;\n    g(&t5);\n    return t5;\n', '    t5 = a4;\n    return t5;\n'):
            src = fn(body, '    int t5;\n')
            self.assertEqual(self.p(src), src)

    def test_again(self):
        once = self.p(fn('    t5 = 0x4;\n    return t5;\n', '    int t5;\n'))
        self.assertEqual(self.p(once), once)

if __name__ == '__main__':
    unittest.main()
