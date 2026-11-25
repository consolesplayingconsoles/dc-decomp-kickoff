"""A call through a cast of a function the unit declares K&R (`extern int F();`) passes as many arguments as the generator saw
registers and stack words set, however many the callee's own definition takes (scripts/tools/5-generated/gen_equiv/rewrites.py
narrow_cast_calls; shrink.py --passes narrow runs it with narrow_calls). Power Stone 2 FUN_0c02e43c: FUN_0c02e078, defined with 3
parameters, was called six times through a 12-int cast, and every call loaded and pushed nine words the callee never reads (the
checker compared them because the cast said so). No game data, no compiler. Stdlib only.

    narrow_cast_calls   narrow   `((int (*)(int, int, int, int, int))(F))(a, b, c, d, e)` with F defined on 3 parameters becomes
                                 `((int (*)(int, int, int))(F))(a, b, c)`
                        float    a float result keeps its type: `((float (*)(int, int))(F))(a, b)` on 1 parameter -> `(int))(F))(a)`
                        two      two calls in one text are both narrowed
                        call     a dropped argument that holds a call: the call is left as it is
                        equal    a definition with as many or more parameters than the cast lists: left
                        types    a cast whose leading types are not the definition's: left
                        unknown  a name with no definition in the given texts: left
                        pointer  a call through a variable (`(p)`) is not a name with a definition: left
                        again    a second run changes nothing
    wired               narrow_unit (the generator's per-unit hook) and shrink.py's narrow pass both call it
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')


class TestCastCalls(unittest.TestCase):
    def setUp(self):
        saved = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved)
        sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import rewrites
        self.rw = rewrites

    def test_narrow(self):
        t = '    t5 = ((int (*)(int, int, int, int, int))(F))(a, b, c, d, e);\n'
        self.assertEqual(self.rw.narrow_cast_calls(t, {'F': ['int', 'int', 'int']}),
                         '    t5 = ((int (*)(int, int, int))(F))(a, b, c);\n')

    def test_float(self):
        t = '    f = ((float (*)(int, int))(F))(a, b);\n'
        self.assertEqual(self.rw.narrow_cast_calls(t, {'F': ['int']}), '    f = ((float (*)(int))(F))(a);\n')

    def test_two(self):
        t = '    ((int (*)(int, int, int))(F))(a, b, c);\n    ((int (*)(int, int))(F))(x, y);\n'
        self.assertEqual(self.rw.narrow_cast_calls(t, {'F': ['int']}),
                         '    ((int (*)(int))(F))(a);\n    ((int (*)(int))(F))(x);\n')

    def test_call_in_dropped_argument_left(self):
        t = '    ((int (*)(int, int))(F))(a, g(b));\n'
        self.assertEqual(self.rw.narrow_cast_calls(t, {'F': ['int']}), t)

    def test_nested_call_in_kept_argument(self):
        t = '    ((int (*)(int, int))(F))(g(a), b);\n'
        self.assertEqual(self.rw.narrow_cast_calls(t, {'F': ['int']}), '    ((int (*)(int))(F))(g(a));\n')

    def test_equal_left(self):
        t = '    ((int (*)(int, int))(F))(a, b);\n'
        self.assertEqual(self.rw.narrow_cast_calls(t, {'F': ['int', 'int']}), t)
        self.assertEqual(self.rw.narrow_cast_calls(t, {'F': ['int', 'int', 'int']}), t)

    def test_types_left(self):
        t = '    ((int (*)(float, int))(F))(a, b);\n'
        self.assertEqual(self.rw.narrow_cast_calls(t, {'F': ['int']}), t)

    def test_unknown_left(self):
        t = '    ((int (*)(int, int))(F))(a, b);\n'
        self.assertEqual(self.rw.narrow_cast_calls(t, {}), t)

    def test_pointer_left(self):
        t = '    ((int (*)(int, int))(p))(a, b);\n'
        self.assertEqual(self.rw.narrow_cast_calls(t, {'F': ['int']}), t)

    def test_again(self):
        t = '    ((int (*)(int, int, int))(F))(a, b, c);\n'
        once = self.rw.narrow_cast_calls(t, {'F': ['int']})
        self.assertEqual(self.rw.narrow_cast_calls(once, {'F': ['int']}), once)

    def test_wired_in_narrow_unit(self):
        src = open(os.path.join(TOOLS, '5-generated', 'gen_equiv', 'rewrites.py')).read()
        self.assertIn('narrow_cast_calls(', src.split('def narrow_unit', 1)[1])

    def test_wired_in_shrink_narrow(self):
        src = open(os.path.join(TOOLS, '7-reduction', 'shrink.py')).read()
        self.assertIn('rewrites.narrow_cast_calls(', src.split('def narrow_pass', 1)[1])


if __name__ == '__main__':
    unittest.main()
