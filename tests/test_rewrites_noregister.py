"""`register` is dropped from declarations (rewrites.py no_register; shrink.py --passes noregister).
No game data, no compiler. Stdlib only.

    no_register  drop      `register int t0;` and `register float u0;` become `int t0;` and `float u0;`
                 other     pointer and short declarations, statements and a name containing the word are left
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
        self.p = getattr(rewrites, 'no_register')

    def test_drop(self):
        self.assertEqual(self.p('    register int t0;\n    register float u0;\n'), '    int t0;\n    float u0;\n')

    def test_other(self):
        for s in ('    register short t0;\n', '    int register_count;\n', '    t0 = register_x;\n', '    int t0;\n'):
            self.assertEqual(self.p(s), s)

    def test_again(self):
        once = self.p('    register int t0;\n')
        self.assertEqual(self.p(once), once)

if __name__ == '__main__':
    unittest.main()
