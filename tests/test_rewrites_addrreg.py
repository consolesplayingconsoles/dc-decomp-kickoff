"""A fixed address dereferenced at many places is held in a register (rewrites.py address_registers; shrink.py --passes addrreg).
No game data, no compiler. Stdlib only.

    address_registers  held     an address dereferenced six times: `register int qa0;`, `qa0 = 0xC123456;` after the declarations, `*(int *)qa0` at the uses
                       two       the two most used addresses at most
                       few       five uses are left
                       other     a plain constant without a dereference is left
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
        self.p = getattr(rewrites, 'address_registers')

    A = '    *(int *)0xC123456 = 1;\n' * 6

    def test_held(self):
        got = self.p(fn(self.A + '    return a4;\n', '    int t1;\n'))
        self.assertIn('    register int qa0;\n', got)
        self.assertIn('    qa0 = 0xC123456;\n', got)
        self.assertEqual(got.count('*(int *)qa0 = 1;'), 6)
        self.assertLess(got.index('int t1;'), got.index('qa0 = 0xC123456;'))

    def test_two(self):
        body = self.A + '    *(int *)0xC654321 = 1;\n' * 7 + '    *(int *)0xC111111 = 1;\n' * 6
        got = self.p(fn(body + '    return a4;\n'))
        self.assertIn('qa0', got)
        self.assertIn('qa1', got)
        self.assertNotIn('qa2', got)

    def test_few(self):
        src = fn('    *(int *)0xC123456 = 1;\n' * 5 + '    return a4;\n')
        self.assertEqual(self.p(src), src)

    def test_other(self):
        src = fn('    t1 = 0xC123456;\n' * 8 + '    return a4;\n', '    int t1;\n')
        self.assertEqual(self.p(src), src)

    def test_again(self):
        once = self.p(fn(self.A + '    return a4;\n'))
        self.assertEqual(self.p(once), once)

if __name__ == '__main__':
    unittest.main()
