"""Frame words become locals only when no slot address is taken, passed or stepped from (rewrites.py stack_locals; shrink.py --passes stklocals). Failures found on real functions: a buffer at stk+8 handed to a callee got the next slots wrong (C36B0000 for C3690000), and a function stepping from one slot into its neighbours ran away over 2,000,000 instructions.
No game data, no compiler. Stdlib only.

    stack_locals  words     slots read and written as whole words at constant offsets become locals, the array gone
                  floats    a slot only read and written as float is a float local
                  types     a slot used as int and as float keeps the more used type, the other read through a cast of its address
                  unsigned  a slot used as unsigned int keeps the unsignedness
                  folded    `((int)stk + 8) + 4` style offsets are summed first
                  buffer    FUN_0c147928: a struct copy and a call on `(((int)stk + 16) + 0x20)` leave the function as it is
                  passed    an address passed to a call leaves it
                  stepped   FUN_0c108d12: an address stepped by a variable leaves it
                  narrow    a short or char access, a volatile read, an index, a struct copy leave it
                  range     a word outside the array leaves it
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
        self.p = getattr(rewrites, 'stack_locals')

    D = '    int stk[8];\n    register int t1;\n'

    def test_words(self):
        got = self.p(fn('    *(int *)((int)stk + 4) = a4;\n    t1 = *(int *)((int)stk + 4);\n    return t1;\n', self.D))
        self.assertNotIn('stk', got)
        self.assertIn('int s4;', got)
        self.assertIn('s4 = a4;', got)
        self.assertIn('t1 = s4;', got)

    def test_floats(self):
        got = self.p(fn('    *(float *)((int)stk + 4) = 1.0f;\n    return 0;\n', self.D))
        self.assertIn('float s4;', got)

    def test_types(self):
        got = self.p(fn('    *(int *)((int)stk + 4) = a4;\n    *(int *)((int)stk + 4) = a4;\n    t1 = *(float *)((int)stk + 4);\n    return 0;\n', self.D))
        self.assertIn('int s4;', got)
        self.assertIn('(*(float *)&s4)', got)

    def test_unsigned(self):
        got = self.p(fn('    *(unsigned int *)((int)stk + 4) = a4;\n    t1 = *(unsigned int *)((int)stk + 4);\n    t1 = *(int *)((int)stk + 4);\n    return 0;\n', self.D))
        self.assertIn('unsigned int s4;', got)
        self.assertIn('t1 = (*(int *)&s4);', got)

    def test_folded(self):
        got = self.p(fn('    *(int *)(((int)stk + 4) + 0x4) = a4;\n    t1 = *(int *)((int)stk + 8);\n    return t1;\n', self.D))
        self.assertNotIn('stk', got)
        self.assertEqual(got.count('s8'), 3)

    def same(self, body):
        src = fn(body, self.D)
        self.assertEqual(self.p(src), src)

    def test_buffer(self):
        # FUN_0c147928: a buffer in the frame reached by address
        self.same('    *(int *)((int)stk + 8) = a4;\n    { struct mv3 { int w[3]; }; *(struct mv3 *)((((int)stk + 16) + 0x20)) = *(struct mv3 *)(0xC2A2640); }\n'
                  '    FUN_0c058adc((((int)stk + 16) + 0x20), (((int)stk + 16) + 0x20), a4);\n    return *(int *)((int)stk + 8);\n')

    def test_passed(self):
        self.same('    *(int *)((int)stk + 8) = a4;\n    h(((int)stk + 8));\n    return 0;\n')

    def test_stepped(self):
        # FUN_0c108d12: the address of one slot stepped into its neighbours
        self.same('    *(int *)((int)stk + 8) = a4;\n    t1 = *(int *)((((int)stk + 8) + (t1 << 2)));\n    return t1;\n')

    def test_narrow(self):
        self.same('    *(short *)((int)stk + 4) = a4;\n    return 0;\n')
        self.same('    *(volatile int *)((int)stk + 4);\n    return 0;\n')
        self.same('    t1 = stk[1];\n    return t1;\n')

    def test_range(self):
        self.same('    *(int *)((int)stk + 32) = a4;\n    return 0;\n')

    def test_again(self):
        once = self.p(fn('    *(int *)((int)stk + 4) = a4;\n    return *(int *)((int)stk + 4);\n', self.D))
        self.assertEqual(self.p(once), once)

if __name__ == '__main__':
    unittest.main()
