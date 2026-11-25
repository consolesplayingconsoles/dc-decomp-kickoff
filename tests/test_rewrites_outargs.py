"""Frame stores of call-pushed words that nothing reads are not written (rewrites.py drop_outargs; shrink.py --passes outargs).
No game data, no compiler. Stdlib only.

    drop_outargs  dead      `*(int *)((int)stk + 8) = t1;` goes when nothing reads or reaches the slot
                  read      a direct load of the slot keeps the store
                  address   an address of the slot, passed on, keeps it
                  call      a store whose value is a call keeps it
                  only      the other slots' stores are kept apart from the dead ones
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
        self.p = getattr(rewrites, 'drop_outargs')

    D = '    int stk[8];\n    register int t1;\n'

    def test_dead(self):
        got = self.p(fn('    *(int *)((int)stk + 8) = t1;\n    *(int *)((int)stk + 12) = t1;\n    h(a4);\n    return a4;\n', self.D))
        self.assertNotIn('+ 8) =', got)
        self.assertNotIn('+ 12) =', got)
        self.assertIn('h(a4);', got)

    def test_read(self):
        src = fn('    *(int *)((int)stk + 8) = t1;\n    t1 = *(int *)((int)stk + 8);\n    return t1;\n', self.D)
        self.assertEqual(self.p(src), src)

    def test_address(self):
        src = fn('    *(int *)((int)stk + 8) = t1;\n    h(((int)stk + 8));\n    return a4;\n', self.D)
        self.assertEqual(self.p(src), src)

    def test_call(self):
        src = fn('    *(int *)((int)stk + 8) = g(t1);\n    return a4;\n', self.D)
        self.assertEqual(self.p(src), src)

    def test_only(self):
        got = self.p(fn('    *(int *)((int)stk + 8) = t1;\n    *(int *)((int)stk + 12) = t1;\n    t1 = *(int *)((int)stk + 12);\n    return t1;\n', self.D))
        self.assertNotIn('+ 8) =', got)
        self.assertIn('+ 12) = t1;', got)

    def test_again(self):
        once = self.p(fn('    *(int *)((int)stk + 8) = t1;\n    return a4;\n', self.D))
        self.assertEqual(self.p(once), once)

if __name__ == '__main__':
    unittest.main()
