"""The signed-remainder fold of generated C (scripts/tools/5-generated/gen_equiv/rewrites.py fold_signed_mask). No game data, no compiler.
Stdlib only.

A remainder by a power of two on a signed value comes out of the generator as an eight-line sign sequence,

    if ((int)t5 >= 0) { t5 = (t5 & 0x3F); } else { t5 = (~t5); t5 = (t5 + 0x1); t5 = (t5 & 0x3F); t5 = (~t5); t5 = (t5 + 0x1); }

which is `t5 % 0x40` (the negative arm is -((-t5) & 0x3F): C's remainder truncates toward zero). SHC compiles the one-liner as the
original did. Power Stone 2 FUN_0c0d0ec2: the sequence was written 16 times in one unit.

    fold_signed_mask   fold      the sequence on an int variable becomes `t5 = (t5 % 0x40);`, whatever the indentation
                       masks     0x3, 0x7F and 0xFF fold to % 0x4, % 0x80, % 0x100
                       unsigned  a variable declared unsigned is left as it is (its remainder is not the signed one)
                       mask      a mask that is not 2^k - 1 (0x3E) is left as it is
                       variable  an else arm that works on another variable is left as it is
                       again     a second run changes nothing
                       two-line  the other shape, `t9 = ((~(((~t5) + 0x1) & 0xF)) + 0x1); if ((int)t5 >= 0) { t9 = (t5 & 0xF); }`
                                 (Power Stone 2 FUN_0c0b2d30: 28 of them), is `t9 = (t5 % 0x10);`
                       two-line unsigned / mask / source   left as it is when t5 is unsigned, the mask is not 2^k - 1, or the
                                 branch tests another variable than the one the first line negates
"""
import os
import sys
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'tools')

SEQ = """    if ((int)%(v)s >= 0) {
        %(v)s = (%(v)s & %(m)s);
    } else {
        %(v)s = (~%(v)s);
        %(v)s = (%(v)s + 0x1);
        %(v)s = (%(v)s & %(m)s);
        %(v)s = (~%(v)s);
        %(v)s = (%(v)s + 0x1);
    }
"""


def unit(body, decl='register int t5;'):
    return 'int f(int a4)\n{\n    %s\n    register int t9;\n%s    return t5;\n}\n' % (decl, body)


class TestSignedMask(unittest.TestCase):
    def setUp(self):
        saved = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved)
        sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import rewrites
        self.fold = rewrites.fold_signed_mask

    def test_fold(self):
        got = self.fold(unit(SEQ % {'v': 't5', 'm': '0x3F'}))
        self.assertIn('    t5 = (t5 % 0x40);\n', got)
        self.assertNotIn('~', got)

    def test_masks(self):
        for mask, rem in (('0x3', '0x4'), ('0x7F', '0x80'), ('0xFF', '0x100')):
            got = self.fold(unit(SEQ % {'v': 't5', 'm': mask}))
            self.assertIn('t5 = (t5 %% %s);' % rem, got, mask)

    def test_unsigned_left(self):
        text = unit(SEQ % {'v': 't5', 'm': '0x3F'}, decl='register unsigned int t5;')
        self.assertEqual(self.fold(text), text)

    def test_other_mask_left(self):
        text = unit(SEQ % {'v': 't5', 'm': '0x3E'})
        self.assertEqual(self.fold(text), text)

    def test_other_variable_left(self):
        text = unit(SEQ % {'v': 't5', 'm': '0x3F'}).replace('t5 = (~t5);\n        t5 = (t5 + 0x1);\n    }', 't5 = (~t9);\n        t5 = (t5 + 0x1);\n    }')
        self.assertEqual(self.fold(text), text)

    def test_again(self):
        once = self.fold(unit(SEQ % {'v': 't5', 'm': '0x3F'}))
        self.assertEqual(self.fold(once), once)


TWO = """    %(d)s = ((~(((~%(s)s) + 0x1) & %(m)s)) + 0x1);
    if ((int)%(t)s >= 0) {
        %(d)s = (%(u)s & %(m)s);
    }
"""


class TestSignedMaskTwoLine(unittest.TestCase):
    def setUp(self):
        saved = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved)
        sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import rewrites
        self.fold = rewrites.fold_signed_mask

    def text(self, decl='register int t5;', **kw):
        v = {'d': 't9', 's': 't5', 't': 't5', 'u': 't5', 'm': '0xF'}
        v.update(kw)
        return unit(TWO % v, decl=decl)

    def test_fold(self):
        got = self.fold(self.text())
        self.assertIn('    t9 = (t5 % 0x10);\n', got)
        self.assertNotIn('~', got)

    def test_unsigned_source_left(self):
        text = self.text(decl='register unsigned int t5;')
        self.assertEqual(self.fold(text), text)

    def test_other_mask_left(self):
        text = self.text(m='0xE')
        self.assertEqual(self.fold(text), text)

    def test_branch_on_another_variable_left(self):
        text = self.text(t='t9')
        self.assertEqual(self.fold(text), text)

    def test_branch_reads_another_variable_left(self):
        text = self.text(u='t9')
        self.assertEqual(self.fold(text), text)

    def test_again(self):
        once = self.fold(self.text())
        self.assertEqual(self.fold(once), once)


if __name__ == '__main__':
    unittest.main()
