"""The frame layout order of locals (rewrites.py order_frame; shrink.py --passes frameorder).
No game data, no compiler. Stdlib only.

    order_frame  regs      the most-named temporaries (seven int, four float) stay `register` and come first, most-named first
                 rest      the others are declared plain, least-named first
                 address   a variable whose address is taken is never `register`
                 few       a function with fewer than two such declarations is left
                 other     the other declaration lines (arrays, initialisers) keep their places
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
        self.p = getattr(rewrites, 'order_frame')

    def decls(self, t):
        return [l.strip() for l in t.split('\n') if l.startswith('    ') and l.strip().endswith(';') and ('int ' in l or 'float ' in l) and '=' not in l and 'return' not in l and 'goto' not in l]

    def test_regs_rest(self):
        names = ['t%d' % i for i in range(9)]
        body = ''.join('    %s = a4;\n' % n + ('    %s = %s;\n' % (n, n)) * i for i, n in enumerate(names))
        got = self.p(fn(body + '    return t0;\n', ''.join('    register int %s;\n' % n for n in names)))
        d = self.decls(got)
        self.assertEqual(d[:7], ['register int t%d;' % i for i in (8, 7, 6, 5, 4, 3, 2)])
        self.assertEqual(d[7:], ['int t0;', 'int t1;'][::-1][::-1] if False else ['int t0;', 'int t1;'])

    def test_address(self):
        got = self.p(fn('    t1 = a4;\n    t1 = t1;\n    g(&t0);\n    return t0;\n', '    register int t0;\n    register int t1;\n'))
        self.assertIn('    int t0;', got)
        self.assertIn('    register int t1;', got)

    def test_few(self):
        src = fn('    t0 = a4;\n    return t0;\n', '    register int t0;\n')
        self.assertEqual(self.p(src), src)

    def test_other(self):
        src = fn('    stk[0] = 1;\n    return t0;\n', '    int stk[4];\n    int t0 = 1;\n')
        self.assertEqual(self.p(src), src)

    def test_again(self):
        names = ['t%d' % i for i in range(9)]
        body = ''.join('    %s = a4;\n' % n + ('    %s = %s;\n' % (n, n)) * i for i, n in enumerate(names))
        once = self.p(fn(body + '    return t0;\n', ''.join('    register int %s;\n' % n for n in names)))
        self.assertEqual(self.p(once), once)

if __name__ == '__main__':
    unittest.main()
