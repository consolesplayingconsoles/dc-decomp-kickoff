"""Functions whose result nobody reads are written `void` (scripts/tools/5-generated/gen_equiv/rewrites.py unused_value_names and
void_returns; shrink.py --passes voidret). The generator threads a value to every `return` of a function the original leaves
nothing meaningful in r0 for (Power Stone 2: a temporary per branch, 10 to 200 `register` temporaries and a copy at each level, in
about half the functions the manual run rewrote), and equiv.py compares r0 only for a C that returns a value, so the C proves either
way; what decides is whether a caller reads it. No game data, no compiler. Stdlib only.

    unused_value_names   bare      a call used as a statement, and declarations and definitions, are not uses: the name is returned
                         used      a call that is assigned, compared, passed or returned is a use: the name is not returned
                         register  the original returns in r0 or fr0 (reg_of says so): not returned, however the callers use it
                         cast      a call through a cast of the name is a statement too
                         unknown   a name reg_of knows nothing about is not returned
    void_returns         value     `return t5;` and `return 0x3C;` become `return;`, the type and the same unit's prototype `void`
                         call      `return F(a, b);` and `return ((int (*)(int))(F))(a);` become the call, then `return;`, same indent
                         other     a function not in the set is left as it is
                         inline    a `return` that is not alone on its line (`if (x) return 1;`) leaves the whole function as it is
                         mixed     `return F(a) + 1;` (a call inside an expression) leaves the whole function as it is
                         pointer   a pointer result is left as it is
                         void      an already void function is left as it is
                         again     a second run changes nothing
    shrink.py            wired     `voidret` is in the default --passes list and in the pass table
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')


class TestVoidRet(unittest.TestCase):
    def setUp(self):
        saved = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved)
        sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import rewrites
        self.rw = rewrites

    # unused_value_names ------------------------------------------------------------------------------------------------------
    def names(self, texts, reg=None):
        return self.rw.unused_value_names(texts, lambda n: (reg or {}).get(n))

    def test_bare_call_is_not_a_use(self):
        t = {'a.c': 'int f(int a4);\nint f(int a4)\n{\n    return a4;\n}\n', 'b.c': 'void g(int a4)\n{\n    f(a4);\n}\n'}
        self.assertEqual(self.names(t), {'f'})

    def test_assigned_call_is_a_use(self):
        t = {'a.c': 'int f(int a4)\n{\n    return a4;\n}\n', 'b.c': 'void g(int a4)\n{\n    int t;\n    t = f(a4);\n}\n'}
        self.assertEqual(self.names(t), set())

    def test_condition_and_argument_and_return_are_uses(self):
        for use in ('    if (f(a4)) {\n    }\n', '    h(f(a4));\n', '    return f(a4);\n'):
            t = {'a.c': 'int f(int a4)\n{\n    return a4;\n}\n', 'b.c': 'int g(int a4)\n{\n%s}\n' % use}
            self.assertNotIn('f', self.names(t), use)

    def test_original_returns_a_value(self):
        t = {'a.c': 'int f(int a4)\n{\n    return a4;\n}\n'}
        self.assertEqual(self.names(t, {'f': 'r0'}), set())
        self.assertEqual(self.names(t, {'f': 'fr0'}), set())

    def test_cast_call_is_a_statement(self):
        t = {'a.c': 'int f(int a4)\n{\n    return a4;\n}\n', 'b.c': 'void g(int a4)\n{\n    ((int (*)(int))(f))(a4);\n}\n'}
        self.assertEqual(self.names(t), {'f'})

    def test_unknown_name(self):
        t = {'a.c': 'int f(int a4)\n{\n    return a4;\n}\n'}
        self.assertEqual(self.rw.unused_value_names(t, lambda n: 'unknown'), set())

    # void_returns ------------------------------------------------------------------------------------------------------------
    def test_value(self):
        t = 'int f(int a4);\n\nint f(int a4)\n{\n    int t5;\n    if (a4) {\n        return 0x3C;\n    }\n    t5 = a4;\n    return t5;\n}\n'
        got = self.rw.void_returns(t, {'f'})
        self.assertIn('void f(int a4);', got)
        self.assertIn('void f(int a4)\n{', got)
        self.assertEqual(got.count('return;'), 2)
        self.assertNotIn('return t5', got)
        self.assertNotIn('0x3C', got)

    def test_call(self):
        t = 'int f(int a4)\n{\n    if (a4) {\n        return g(a4, 0x7);\n    }\n    return ((int (*)(int, int))(h))(a4, 0x1);\n}\n'
        got = self.rw.void_returns(t, {'f'})
        self.assertIn('        g(a4, 0x7);\n        return;\n', got)
        self.assertIn('    ((int (*)(int, int))(h))(a4, 0x1);\n    return;\n', got)

    def test_other_function_left(self):
        t = 'int f(int a4)\n{\n    return a4;\n}\nint g(int a4)\n{\n    return a4;\n}\n'
        got = self.rw.void_returns(t, {'f'})
        self.assertIn('int g(int a4)\n{\n    return a4;\n}', got)
        self.assertIn('void f(int a4)', got)

    def test_inline_return_left(self):
        t = 'int f(int a4)\n{\n    if (a4) return 1;\n    return 0;\n}\n'
        self.assertEqual(self.rw.void_returns(t, {'f'}), t)

    def test_call_inside_an_expression_left(self):
        t = 'int f(int a4)\n{\n    return g(a4) + 1;\n}\n'
        self.assertEqual(self.rw.void_returns(t, {'f'}), t)

    def test_pointer_left(self):
        t = 'int *f(int a4)\n{\n    return 0;\n}\n'
        self.assertEqual(self.rw.void_returns(t, {'f'}), t)

    def test_void_left(self):
        t = 'void f(int a4)\n{\n    return;\n}\n'
        self.assertEqual(self.rw.void_returns(t, {'f'}), t)

    def test_again(self):
        t = 'int f(int a4)\n{\n    if (a4) {\n        return g(a4);\n    }\n    return 0;\n}\n'
        once = self.rw.void_returns(t, {'f'})
        self.assertEqual(self.rw.void_returns(once, {'f'}), once)

    def test_wired_in_shrink(self):
        src = open(os.path.join(TOOLS, '7-reduction', 'shrink.py')).read()
        self.assertIn("'deadframe', 'smod', 'voidret']", src)
        self.assertIn("'voidret':", src)
        self.assertIn('rewrites.void_returns(', src)


if __name__ == '__main__':
    unittest.main()
