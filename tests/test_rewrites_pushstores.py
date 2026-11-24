"""Frame stores that the call also passes (scripts/tools/5-generated/gen_equiv/rewrites.py drop_pushed_stores). No game data, no
compiler. Stdlib only.

The words a caller pushes for a call (arguments past the fourth) are written by the generator twice: as stores into the frame array,
`*(int *)((int)stk + 8) = t1;`, and as the call's own arguments, `f(buf, a5, a6, a7, 0xC1B733C, t3, t1)`. The compiler then pushes the
words itself and also stores them in the frame (5.7 bytes a store, 7,146 bytes over 143 functions of a studio's own game compiled and
read back). A store the call carries is not needed when nothing reads the slot.

    drop_pushed_stores   gone      a store in the run of stores right before a call, whose value is one of the call's arguments past
                                   the fourth, and whose slot nothing else reads, is removed
                         buffer    an address built on the slot's neighbour above the pushed words (`((int)stk + 0) + 0x10`) does not
                                   read the slot and does not block the drop
                         read      a slot read anywhere else (a load of it, or an address that can reach it) keeps its store
                         value     a store whose value is not an argument of the call stays (the callee may read it off the stack)
                         early     a value among the first four arguments does not count: those are registers
                         apart     a statement between the stores and the call: nothing changes
                         odd       a use of `stk` in a form this pass does not know (a bare name, a nested offset): the function is left alone
                         again     a second run changes nothing
"""
import os
import sys
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'tools')

HEAD = 'int f(int a4, int a5, int a6, int a7)\n{\n    int stk[68];\n    register int t1;\n    register int t3;\n\n'


def fn(body, tail='    return a4;\n'):
    return HEAD + body + tail + '}\n'


STORES = ('    t1 = (*(signed char *)0xC542B8B);\n    *(int *)((int)stk + 8) = t1;\n    t3 = (*(signed char *)0xC542B8A);\n'
          '    *(int *)((int)stk + 4) = t3;\n    *(int *)((int)stk + 0) = 0xC1B733C;\n')
CALL = '    g((((int)stk + 0) + 0x10), a5, a6, a7, 0xC1B733C, t3, t1);\n'


class TestPushStores(unittest.TestCase):
    def setUp(self):
        saved = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved)
        sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import rewrites
        self.d = rewrites.drop_pushed_stores

    def test_gone(self):
        got = self.d(fn(STORES + CALL))
        self.assertNotIn('(int)stk + 8) =', got)
        self.assertNotIn('(int)stk + 4) =', got)
        self.assertNotIn('(int)stk + 0) = 0xC1B733C', got)
        self.assertIn('t1 = (*(signed char *)0xC542B8B);', got)
        self.assertIn(CALL, got)

    def test_read(self):
        src = fn(STORES + CALL, tail='    return (*(int *)(((int)stk + 8)));\n')
        got = self.d(src)
        self.assertIn('*(int *)((int)stk + 8) = t1;', got)
        self.assertNotIn('(int)stk + 4) =', got)

    def test_address(self):
        got = self.d(fn(STORES + CALL, tail='    return (((int)stk + 4) + 0x0);\n'))
        self.assertIn('(int)stk + 4) = t3;', got)

    def test_value(self):
        src = fn(STORES.replace('t3 = (*(signed char *)0xC542B8A);\n    *(int *)((int)stk + 4) = t3;', 't3 = (*(signed char *)0xC542B8A);\n    *(int *)((int)stk + 4) = a4;') + CALL)
        got = self.d(src)
        self.assertIn('*(int *)((int)stk + 4) = a4;', got)
        self.assertNotIn('(int)stk + 8) =', got)

    def test_early(self):
        src = fn('    *(int *)((int)stk + 4) = a5;\n    g((((int)stk + 0) + 0x10), a5, a6, a7);\n')
        self.assertEqual(self.d(src), src)

    def test_apart(self):
        for mid in ('    h();\n', '    if (t1 != 0) {\n        t3 = 0;\n    }\n', 'L1:;\n'):
            src = fn(STORES + mid + CALL)
            self.assertEqual(self.d(src), src)

    def test_value_changes(self):
        got = self.d(fn(STORES + '    t1 = (t1 + 0x1);\n' + CALL))
        self.assertIn('*(int *)((int)stk + 8) = t1;', got)
        self.assertNotIn('(int)stk + 4) =', got)

    def test_odd(self):
        src = fn(STORES + CALL, tail='    return (((int)stk + 8) + 0x2 + 0x4);\n')
        self.assertEqual(self.d(src), src)
        src = fn(STORES + CALL, tail='    h(stk);\n    return a4;\n')
        self.assertEqual(self.d(src), src)

    def test_again(self):
        once = self.d(fn(STORES + CALL))
        self.assertEqual(self.d(once), once)

    def test_two_functions(self):
        a = fn(STORES + CALL)
        got = self.d(a + '\n' + a.replace('int f(', 'int k('))
        self.assertEqual(got.count('(int)stk + 8) ='), 0)


if __name__ == '__main__':
    unittest.main()
