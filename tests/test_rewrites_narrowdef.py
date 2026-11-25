"""DESIGN ONLY, not implemented: narrowing a function DEFINITION whose trailing integer parameters nothing references
(scripts/tools/5-generated/gen_equiv/rewrites.py narrow_definitions, not written). The cases below state what it must do; each is an
expected failure until the function exists, and the report that goes with them says why it was not written yet.

The generator sizes a definition's parameters from the registers the original reads (r4-r7) and the stack words; a function that
loads a4 and nothing else is still written with four when the reader saw r5-r7 touched on one path (Power Stone 2: 200 of 9,779
definitions have trailing a5-a7 their body never names, e.g. FUN_0c0fadbc, FUN_0c05cba4, FUN_0c0453f0). narrow_calls then keeps every
call of them at four arguments, and the checker compares the callers on r5-r7.

It is NOT safe for every such function. FUN_0c03f346 looks like a function that reads one argument, but its body hands a5-a7 on to an
indirect call (`((int (*)(int, int, int, int))(table[...]))(t3, a5, a6, a7)`), so the callers' leftover r5-r7 reach the handlers: the
check on them is right. A definition may only be narrowed when no trailing parameter appears anywhere in the body, as an argument of
any call (direct, through a cast, through a pointer or a tail call), in an expression or in a store.

    narrow_definitions   one      only a4 referenced of four parameters: {F: 1}
                         middle   a5 referenced, a6 and a7 not: {F: 2}
                         passed   a7 passed to a direct call: left
                         indirect a5-a7 passed to an indirect call (FUN_0c03f346's shape): left
                         tail     a thunk passing all four on: left
                         floats   float and Stk parameters are not counted or removed
                         extern   a K&R extern with no definition has nothing to narrow
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')


def fn(params, body):
    return 'int F(%s)\n{\n%s}\n' % (params, body)


class TestNarrowDefinitions(unittest.TestCase):
    def setUp(self):
        saved = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved)
        sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import rewrites
        self.nd = getattr(rewrites, 'narrow_definitions', None)      # design only: not written yet

    @unittest.expectedFailure
    def test_one(self):
        self.assertEqual(self.nd({'a.c': fn('int a4, int a5, int a6, int a7', '    return a4;\n')}), {'F': 1})

    @unittest.expectedFailure
    def test_middle(self):
        self.assertEqual(self.nd({'a.c': fn('int a4, int a5, int a6, int a7', '    return a4 + a5;\n')}), {'F': 2})

    @unittest.expectedFailure
    def test_passed_to_a_direct_call_left(self):
        self.assertEqual(self.nd({'a.c': fn('int a4, int a5, int a6, int a7', '    return G(a4, a7);\n')}), {})

    @unittest.expectedFailure
    def test_indirect_call_left(self):
        body = '    return ((int (*)(int, int, int, int))(*(int *)(0xC240284)))(a4, a5, a6, a7);\n'
        self.assertEqual(self.nd({'a.c': fn('int a4, int a5, int a6, int a7', body)}), {})

    @unittest.expectedFailure
    def test_thunk_left(self):
        self.assertEqual(self.nd({'a.c': fn('int a4, int a5, int a6, int a7', '    return G(a4, a5, a6, a7);\n')}), {})

    @unittest.expectedFailure
    def test_floats_and_stk_not_counted(self):
        t = 'int F(int a4, int a5, float f4)\n{\n    return a4;\n}\n'
        self.assertEqual(self.nd({'a.c': t}), {'F': 1})

    @unittest.expectedFailure
    def test_extern_has_nothing(self):
        self.assertEqual(self.nd({'a.c': 'extern int F();\n'}), {})


if __name__ == '__main__':
    unittest.main()
