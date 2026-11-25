"""A field read at an offset as a member of a one-field structure (rewrites.py member_form; splice declares the structures; shrink.py --passes memberform). Failures found on real functions: unbalanced parentheses (the call s own `)` taken with the access), a cast written without outer parentheses (compiler error 2204) after stklocals or fold, and the structure declarations written ahead of the function s `{`.
No game data, no compiler. Stdlib only.

    member_form  member    `*(int *)((a4 + 0x38))` becomes `(((struct o38_int *)(a4))->v)`
                 types     int, unsigned int, float, short, unsigned short, char, unsigned char
                 balance   FUN_0c090158: a call's own `)` right after the access stays: `f((*(int *)((a4 + 0x38))))` keeps its parentheses
                 whole     every member is one parenthesised expression `(((struct oK_T *)(x))->v)`, also after fold_offsets and stack_locals
                 head      no declaration is written into the function text; splice puts them after the unit head, `{` follows the head line
                 alone     a pointer or array base, a misaligned offset, offset 0, a volatile access, a variable offset, `(int)stk` are left
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
        for d in ('common', '7-reduction'):
            sys.path.insert(0, os.path.join(TOOLS, d))
        import toolpath  # noqa: F401
        import rewrites
        self.rw = rewrites
        self.p = getattr(rewrites, 'member_form')

    SRC = 'int f(int a4)\n{\n    int t1;\n    t1 = math_cos_angle16((*(int *)((a4 + 0x38))));\n    *(float *)((a4 + 0x54)) = (t1 * *(float *)(a4 + 0x4C));\n    return t1;\n}\n'

    def balanced(self, t):
        for l in t.split('\n'):
            self.assertEqual(l.count('('), l.count(')'), l)

    def test_member(self):
        got = self.p('t = *(int *)((a4 + 0x38));')
        self.assertEqual(got, 't = (((struct o38_int *)(a4))->v);')

    def test_types(self):
        for ty, nm, k in (('unsigned int', 'uint', 4), ('float', 'float', 4), ('short', 'short', 2), ('unsigned short', 'ushort', 2), ('char', 'char', 1), ('unsigned char', 'uchar', 1)):
            self.assertEqual(self.p('t = *(%s *)((a4 + 0x%X));' % (ty, 8 * k)), 't = (((struct o%X_%s *)(a4))->v);' % (8 * k, nm))

    def test_balance(self):
        got = self.p(self.SRC)
        self.balanced(got)
        self.assertIn('math_cos_angle16(((((struct o38_int *)(a4))->v)));', got)
        self.assertIn('(((struct o54_float *)(a4))->v) = (t1 * (((struct o4C_float *)(a4))->v));', got)

    def test_after_fold(self):
        # FUN_0c090158: after fold the offset is a single-parenthesis sum, and the access took the call's `)` with it
        src = 'int f(int a4)\n{\n    t1 = ((math_cos_angle16((*(int *)(((a4 + 0x40) - 0x8))))) * t2);\n}\n'
        got = self.p(self.rw.fold_offsets(src))
        self.balanced(got)
        self.assertIn('t1 = ((math_cos_angle16(((((struct o38_int *)(a4))->v)))) * t2);', got)

    def test_whole(self):
        for pre in (lambda t: t, self.rw.fold_offsets, self.rw.stack_locals):
            got = self.p(pre(self.SRC.replace('(a4 + 0x38)', '((a4 + 0x40) - 0x8)')))
            self.balanced(got)
            self.assertEqual(got.count('->v'), len(__import__('re').findall(r'\(\(\(struct o[0-9A-F]+_\w+ \*\)\(\w+\)\)->v\)', got)))

    def test_head(self):
        got = self.p(self.SRC)
        self.assertNotIn('struct o38_int {', got)
        self.assertTrue(got.startswith('int f(int a4)\n{\n'))
        unit = '/* unit */\nextern int g(int);\n\n' + self.SRC.replace('t1 = math_cos_angle16(', 't1 = (')
        out = self.rw.splice(unit, {'f': got})
        self.assertIn('struct o38_int { char p[0x38]; int v; };', out)
        self.assertLess(out.index('struct o38_int {'), out.index('int f(int a4)\n{\n'))
        self.assertEqual(out.count('struct o38_int {'), 1)

    def test_alone(self):
        for s in ('t = *(int *)((p + 0x10));', 't = *(int *)((a4 + 0x3));', 't = *(int *)(a4);', 't = *(int *)((a4 + 0x0));',
                  't = *(volatile int *)((a4 + 0x38));', 't = *(int *)((a4 + t1));', 't = *(int *)((int)stk + 8);', 't = *(int *)((0xC00 + 0x38));'):
            src = 'int f(int *p, int a4)\n{\n    int t;\n    ' + s + '\n}\n'
            self.assertEqual(self.p(src), src, s)

    def test_again(self):
        once = self.p(self.SRC)
        self.assertEqual(self.p(once), once)

if __name__ == '__main__':
    unittest.main()
