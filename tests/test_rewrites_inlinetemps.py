"""A temporary set once and read in the statements right after is written into its use (rewrites.py inline_temps; shrink.py --passes inlinetemps).
No game data, no compiler. Stdlib only.

    inline_temps  once      a temporary read once straight after its assignment is written into the use, its declaration gone
                  store     a store between the assignment and the use keeps the temporary
                  operand   a change of an operand between them keeps the temporary
                  several   a computed value read twice stays; a plain constant read twice is written into both
                  call      a value that holds a call stays
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
        self.p = getattr(rewrites, 'inline_temps')

    def test_once(self):
        got = self.p(fn('    t3 = (a4 + 0x4);\n    return t3;\n', '    register int t3;\n'))
        self.assertIn('return (a4 + 0x4);', got)
        self.assertNotIn('t3', got)

    def test_store(self):
        src = fn('    t3 = (a4 + 0x4);\n    *(int *)(a4) = 0;\n    return t3;\n', '    register int t3;\n')
        self.assertEqual(self.p(src), src)

    def test_operand(self):
        src = fn('    t3 = (a4 + 0x4);\n    a4 = 0;\n    return t3;\n', '    register int t3;\n')
        self.assertEqual(self.p(src), src)

    def test_several(self):
        src = fn('    t3 = (a4 + 0x4);\n    t4 = (t3 + t3);\n    return t4;\n', '    register int t3;\n    register int t4;\n')
        self.assertEqual(self.p(src).count('t3'), 4)
        got = self.p(fn('    t3 = 0x10;\n    t4 = (t3 + t3);\n    return t4;\n', '    register int t3;\n    register int t4;\n'))
        self.assertNotIn('t3', got)

    def test_call(self):
        src = fn('    t3 = g(a4);\n    return t3;\n', '    register int t3;\n')
        self.assertEqual(self.p(src), src)

    def test_again(self):
        once = self.p(fn('    t3 = (a4 + 0x4);\n    return t3;\n', '    register int t3;\n'))
        self.assertEqual(self.p(once), once)

if __name__ == '__main__':
    unittest.main()
