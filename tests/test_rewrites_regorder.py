"""The `register` declarations in order of use (scripts/tools/5-generated/gen_equiv/rewrites.py order_registers). No game data, no
compiler. Stdlib only.

SHC hands its saved registers (seven integer, four float) to `register` variables in the order they are declared; the ones declared
after those are gone live in the frame. The generator declares its temporaries in the order it made them, so in a long function the
ones a loop names forty times went to the frame behind ones named twice (a game's own source compiled, read back and compiled again:
4,138 of 16,400 excess bytes over 98 functions, 1,656 in one function). The order of declarations of variables with no initialiser
changes nothing in what the C does.

    order_registers   uses       the `register` declarations of a function are written most-named first
                      ties       variables named equally often keep the order they had
                      slots      the lines stay where `register` declarations were: a plain declaration between them keeps its place
                      kinds      int, unsigned int, float and pointer temporaries are ordered together (each kind keeps its own
                                 registers, so only the order within a kind matters)
                      init       a declaration with an initialiser is left where it is (its place can matter)
                      apart      each function of a file is ordered by its own body
                      few        a function with fewer than two such declarations is left as it is
                      again      a second run changes nothing
"""
import os
import sys
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'tools')

FN = '''int f(int a4)
{
    register int t0;
    register int t1;
    int stk[4];
    register float u0;
    register int t2;

    t0 = a4;
    t1 = (t0 + 0x1);
    t2 = (t1 + t1);
    t2 = (t2 + t1);
    u0 = (float)t2;
    u0 = u0 * u0;
    u0 = u0 + u0;
    return t2;
}
'''


class TestOrderRegisters(unittest.TestCase):
    def setUp(self):
        saved = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved)
        sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import rewrites
        self.o = rewrites.order_registers

    def decls(self, text):
        return [l.strip() for l in text.split('\n') if l.startswith('    ') and l.strip().endswith(';') and ('register' in l or 'stk' in l) and '=' not in l]

    def test_uses_and_slots(self):
        got = self.decls(self.o(FN))
        # named: u0 6, t2 5, t1 4, t0 2; the array keeps the third place
        self.assertEqual(got, ['register float u0;', 'register int t2;', 'int stk[4];', 'register int t1;', 'register int t0;'])

    def test_body_unchanged(self):
        a, b = FN.split('\n\n', 1)[1], self.o(FN).split('\n\n', 1)[1]
        self.assertEqual(a, b)

    def test_ties(self):
        src = 'int f(int a4)\n{\n    register int t0;\n    register int t1;\n    register int t2;\n\n    t0 = a4;\n    t1 = a4;\n    t2 = a4;\n    t2 = t2;\n    return t0;\n}\n'
        got = self.decls(self.o(src))
        self.assertEqual(got, ['register int t2;', 'register int t0;', 'register int t1;'])

    def test_kinds(self):
        src = ('int f(int a4)\n{\n    register unsigned int t0;\n    register int *t1;\n    register float u0;\n\n'
               '    t0 = a4;\n    t1 = (int *)a4;\n    *t1 = t0;\n    t1 = t1;\n    u0 = 1.0f;\n    u0 = u0 + u0;\n    u0 = u0 * u0;\n    return 0;\n}\n')
        got = self.decls(self.o(src))
        self.assertEqual(got, ['register float u0;', 'register int *t1;', 'register unsigned int t0;'])

    def test_init(self):
        src = 'int f(int a4)\n{\n    register int t0 = a4;\n    register int t1;\n    register int t2;\n\n    t1 = t0;\n    t2 = t1;\n    t2 = (t2 + t2);\n    return t2;\n}\n'
        got = self.o(src)
        self.assertTrue(got.index('register int t0 = a4;') < got.index('register int t2;') < got.index('register int t1;'))

    def test_apart(self):
        g = FN.replace('int f(', 'int g(').replace('t2 = (t2 + t1);\n', 't0 = t0;\n    t0 = t0;\n    t0 = t0;\n    t0 = t0;\n')
        got = self.o(FN + '\n' + g)
        first, second = got.split('int g(')
        self.assertEqual(self.decls(first)[0], 'register float u0;')
        self.assertEqual(self.decls(second)[0], 'register int t0;')

    def test_few(self):
        src = 'int f(int a4)\n{\n    register int t0;\n\n    t0 = a4;\n    return t0;\n}\n'
        self.assertEqual(self.o(src), src)

    def test_again(self):
        once = self.o(FN)
        self.assertEqual(self.o(once), once)


if __name__ == '__main__':
    unittest.main()
