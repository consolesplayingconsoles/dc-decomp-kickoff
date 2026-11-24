"""A temporary assigned again in the same straight-line run is written into its uses (scripts/tools/5-generated/gen_equiv/rewrites.py rt_fold; shrink.py --passes rtfold).
No game data, no compiler. Stdlib only.

    rt_fold   run       `t5 = t1; t5 = (t5 << 1); t5 = (t5 + t1);` becomes one assignment
              store     a loaded value is not moved past a store
              operand   a value is not moved past a change of one of its operands
              brace     nothing is folded across a brace
              address   a name whose address is taken is left
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
        self.p = getattr(rewrites, 'rt_fold')

    D = '    int t1;\n    int t5;\n    int t6;\n'

    def test_run(self):
        got = self.p(fn('    t1 = a4;\n    t5 = t1;\n    t5 = (t5 << 1);\n    t5 = (t5 + t1);\n    return t5;\n', self.D))
        self.assertEqual(got.count('t5 = '), 1)
        self.assertIn('t5 = ((t1 << 1) + t1);', got)

    def test_store(self):
        src = fn('    t5 = *(int *)((a4 + 0x4));\n    *(int *)(a4) = 0;\n    t5 = (t5 + 0x1);\n    return t5;\n', self.D)
        self.assertEqual(self.p(src), src)

    def test_operand(self):
        src = fn('    t5 = (t1 + 0x1);\n    t1 = 0;\n    t6 = t5;\n    t5 = 0;\n    return t6;\n', self.D)
        self.assertEqual(self.p(src), src)

    def test_brace(self):
        src = fn('    t5 = t1;\n    if (a4) {\n        t6 = t5;\n    }\n    t5 = 0;\n    return t6;\n', self.D)
        self.assertEqual(self.p(src), src)

    def test_address(self):
        src = fn('    t5 = t1;\n    g(&t5);\n    t5 = (t5 + t1);\n    return t5;\n', self.D)
        self.assertEqual(self.p(src), src)

    def test_again(self):
        once = self.p(fn('    t5 = t1;\n    t5 = (t5 << 1);\n    t5 = (t5 + t1);\n    return t5;\n', self.D))
        self.assertEqual(self.p(once), once)

if __name__ == '__main__':
    unittest.main()
