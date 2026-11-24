"""Locals that are declared and never named again (scripts/tools/5-generated/gen_equiv/rewrites.py drop_unused_locals). No game data,
no compiler. Stdlib only.

The generator declares a variable for every register it tracked, also the ones no statement ends up naming (a pseudo-register, a
flag folded away, a temporary an earlier pass removed the uses of), and declares them `register`. In a small function the compiler
ignores them. In a large one they take part in handing out its saved registers and frame slots: deleting 11 such lines took one
function of a game's own source, read back and compiled again, from 7,144 to 5,434 bytes, and 308 from another. A declaration nothing
refers to changes nothing in what the C does.

    drop_unused_locals   gone      a scalar declaration (`register` or not) whose name appears nowhere else in the function is removed
                         kept      one that is named anywhere else stays, where it was
                         word      t1 is not named by t10 or by at1
                         init      a declaration with an initialiser stays (its expression may call)
                         array     an array or a structure declaration is not this pass's business
                         apart     each function is judged by its own body: a name used only in another function is unused here
                         again     a second run changes nothing
"""
import os
import sys
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'tools')


def fn(decls, body, name='f'):
    return 'int %s(int a4)\n{\n%s\n%s    return a4;\n}\n' % (name, ''.join('    %s\n' % d for d in decls), body)


class TestDropUnused(unittest.TestCase):
    def setUp(self):
        saved = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved)
        sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import rewrites
        self.d = rewrites.drop_unused_locals

    def test_gone_and_kept(self):
        src = fn(['register int t0;', 'register int R5;', 'float F9;', 'register float u0;', 'int T_;'],
                 '    t0 = a4;\n    u0 = (float)t0;\n')
        got = self.d(src)
        for gone in ('R5', 'F9', 'T_'):
            self.assertNotIn(gone, got)
        self.assertIn('    register int t0;\n    register float u0;\n', got)
        self.assertIn('    t0 = a4;\n    u0 = (float)t0;\n', got)

    def test_word(self):
        src = fn(['register int t1;', 'register int t10;', 'register int at1;'], '    t10 = a4;\n    at1 = t10;\n')
        got = self.d(src)
        self.assertNotIn('register int t1;', got)
        self.assertIn('register int t10;', got)
        self.assertIn('register int at1;', got)

    def test_init_and_array(self):
        src = fn(['int t0 = g();', 'int stk[4];', 'struct s v;', 'register int *t2;'], '')
        got = self.d(src)
        self.assertIn('int t0 = g();', got)
        self.assertIn('int stk[4];', got)
        self.assertIn('struct s v;', got)
        self.assertNotIn('t2', got)

    def test_apart(self):
        a = fn(['register int t0;', 'register int t1;'], '    t0 = a4;\n')
        b = fn(['register int t0;', 'register int t1;'], '    t1 = a4;\n', name='g')
        got = self.d(a + '\n' + b)
        first, second = got.split('int g(')
        self.assertIn('register int t0;', first)
        self.assertNotIn('register int t1;', first)
        self.assertIn('register int t1;', second)
        self.assertNotIn('register int t0;', second)

    def test_unchanged_and_again(self):
        src = fn(['register int t0;'], '    t0 = a4;\n')
        self.assertEqual(self.d(src), src)
        once = self.d(fn(['register int t0;', 'register int t9;'], '    t0 = a4;\n'))
        self.assertEqual(self.d(once), once)


if __name__ == '__main__':
    unittest.main()
