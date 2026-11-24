"""The interrupt-mask fold of generated C (scripts/tools/5-generated/gen_equiv/rewrites.py fold_imask). No game data, no compiler.
Stdlib only.

The generator reads `set_imask(x)` back from the SR arithmetic the builtin itself compiles to (and #15, shll2, shll2, or into SR)
and writes that arithmetic into the argument: `_builtin_set_imask(((unsigned int)(((t4 & 0xF) << 2) << 2) >> 4));`. The builtin
masks with 15 and shifts again, so the compiler emits the mask and the shifts twice (10 bytes a use, measured on the library's own
source against its bytes).

    fold_imask   fold     the argument `((unsigned int)(((X & 0xF) << 2) << 2) >> 4)` becomes X, for a variable or an expression
                 other    another argument (a constant, a variable, another mask or shift) is left as it is
                 again    a second run changes nothing
"""
import os
import sys
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'tools')


class TestImask(unittest.TestCase):
    def setUp(self):
        saved = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved)
        sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import rewrites
        self.fold = rewrites.fold_imask

    def test_fold(self):
        got = self.fold('    _builtin_set_imask(((unsigned int)(((t4 & 0xF) << 2) << 2) >> 4));\n')
        self.assertEqual(got, '    _builtin_set_imask(t4);\n')

    def test_expression(self):
        src = '        _builtin_set_imask(((unsigned int)((((unsigned short)(*(short *)(((int)stk + 0))) & 0xF) << 2) << 2) >> 4));\n'
        self.assertEqual(self.fold(src), '        _builtin_set_imask((unsigned short)(*(short *)(((int)stk + 0))));\n')

    def test_other(self):
        for src in ('    _builtin_set_imask(0xF);\n', '    _builtin_set_imask(t1);\n',
                    '    _builtin_set_imask(((unsigned int)(((t4 & 0x7) << 2) << 2) >> 4));\n',
                    '    _builtin_set_imask(((unsigned int)(((t4 & 0xF) << 2) << 1) >> 4));\n',
                    '    t5 = ((unsigned int)(((t4 & 0xF) << 2) << 2) >> 4);\n'):
            self.assertEqual(self.fold(src), src)

    def test_again(self):
        once = self.fold('    _builtin_set_imask(((unsigned int)(((t4 & 0xF) << 2) << 2) >> 4));\n')
        self.assertEqual(self.fold(once), once)


if __name__ == '__main__':
    unittest.main()
