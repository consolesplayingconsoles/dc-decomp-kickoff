"""A call through a function-pointer cast that is handed frame words after its register arguments keeps the register arguments (rewrites.py trim_stack_args; shrink.py --passes trimstk).
No game data, no compiler. Stdlib only.

    trim_stack_args  trim      the frame words go from the call and the cast type is cut to match
                     plain     a call with register arguments only is left
                     direct    a direct call (no pointer cast) is left
                     first     a frame word among the first arguments leaves the call alone (nothing to keep)
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
        self.p = getattr(rewrites, 'trim_stack_args')

    CALL = '    t1 = ((int (*)(int, int, int, int, int, int))(a4))(t2, t3, t4, t5, *(int *)((int)stk + 8 + 4), *(int *)((int)stk + 8 + 8));\n'

    def test_trim(self):
        got = self.p(fn(self.CALL))
        self.assertIn('t1 = ((int (*)(int, int, int, int))(a4))(t2, t3, t4, t5);', got)

    def test_plain(self):
        src = fn('    t1 = ((int (*)(int, int))(a4))(t2, t3);\n')
        self.assertEqual(self.p(src), src)

    def test_direct(self):
        src = fn('    t1 = g(t2, t3, t4, t5, *(int *)((int)stk + 8 + 4));\n')
        self.assertEqual(self.p(src), src)

    def test_first(self):
        src = fn('    t1 = ((int (*)(int, int))(a4))(*(int *)((int)stk + 8 + 4), t3);\n')
        self.assertEqual(self.p(src), src)

    def test_again(self):
        once = self.p(fn(self.CALL))
        self.assertEqual(self.p(once), once)

if __name__ == '__main__':
    unittest.main()
