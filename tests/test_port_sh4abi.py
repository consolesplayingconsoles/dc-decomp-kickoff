#!/usr/bin/env python3
"""Where the SH-4 puts a function's arguments, as the port's call check reads a declaration (scripts/tools/10-port/sh4abi.py).
No game data, no compiler. Stdlib only.

    types      a parameter list gives its types with the names dropped: `(int a, float *p, unsigned n)`; `()` is unknown (None),
               `(void)` is none ([]); an array parameter is a pointer, a function pointer is int-sized
    kinds      ints, pointers and the SDK's integer names are int-sized; float and double are floats; `StkN` is a structure of N
               words; a type the tool does not know has no kind
    ints       the first four int-sized arguments go in r4-r7, the fifth in stack word 0
    floats     floats go in fr4-fr11 on their own count: `(int, float, int, float)` is r4, fr4, r5, fr5
    structure  a structure argument is copied to the stack whatever came before it, and the arguments after it keep their
               registers: `(int, Stk3, int)` is r4, stack words 0-2, r5. This is the order x86-64 does not keep, the reason
               a call whose declaration lists them in another order than the definition must be rewritten for the host
    sret       a function that returns a structure gets the address for it as stack word 0: its first stack argument is word 1
    unknown    a parameter of unknown kind, or `...`, gives no layout (None): such a call is left alone
    pointer    a caller's prototype rewritten to the definition's types names no type the caller's file does not know: the
               definition's `Vec3 *` (a type of camera.c) is `void *` in a file without Vec3, which passes the same way;
               a type the file has, and `struct x *`, stay as they are
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')
sys.path.insert(0, os.path.join(TOOLS, '10-port'))
sys.path.insert(0, TOOLS)
import sh4abi  # noqa: E402


class Sh4Abi(unittest.TestCase):
    def test_types(self):
        self.assertEqual(sh4abi.param_types('int a, float *p, unsigned n'), ['int', 'float *', 'unsigned'])
        self.assertIsNone(sh4abi.param_types(''))
        self.assertEqual(sh4abi.param_types('void'), [])
        self.assertEqual(sh4abi.param_types('int v[4]'), ['int *'])
        self.assertEqual(sh4abi.kind(sh4abi.param_types('int v[4]')[0]), 'i')
        self.assertEqual(sh4abi.kind(sh4abi.param_types('unsigned n')[0]), 'i')
        self.assertEqual(sh4abi.param_types('void (*cb)(int, int), int n'), ['int*', 'int'])

    def test_kinds(self):
        for t in ('int', 'unsigned int', 'char *', 'Sint32', 'Uint8', 'const short'):
            self.assertEqual(sh4abi.kind(t), 'i', t)
        self.assertEqual(sh4abi.kind('float'), 'f')
        self.assertEqual(sh4abi.kind('double'), 'f')
        self.assertEqual(sh4abi.kind('Stk3'), ('s', 3))
        self.assertIsNone(sh4abi.kind('AngleR'))

    def test_ints(self):
        self.assertEqual(sh4abi.slots('int', ['int'] * 5),
                         [('r4', 'i'), ('r5', 'i'), ('r6', 'i'), ('r7', 'i'), (('s', 0), 'i')])

    def test_floats(self):
        self.assertEqual(sh4abi.slots('int', ['int', 'float', 'int', 'float']),
                         [('r4', 'i'), ('fr4', 'f'), ('r5', 'i'), ('fr5', 'f')])

    def test_structure(self):
        self.assertEqual(sh4abi.slots('int', ['int', 'Stk3', 'int']),
                         [('r4', 'i'), (('s', 0), ('s', 3)), ('r5', 'i')])
        # the same three arguments in another order land in the same places on the SH-4
        self.assertEqual(sorted(map(str, sh4abi.slots('int', ['Stk3', 'int', 'int']))),
                         sorted(map(str, sh4abi.slots('int', ['int', 'Stk3', 'int']))))

    def test_sret(self):
        self.assertEqual(sh4abi.slots('Stk3', ['int', 'Stk2']), [('r4', 'i'), (('s', 1), ('s', 2))])

    def test_unknown(self):
        self.assertIsNone(sh4abi.slots('int', ['int', 'AngleR']))
        self.assertIsNone(sh4abi.slots('int', ['int', '...']))


class Pointer(unittest.TestCase):
    CALLER = ('typedef struct { int w[3]; } Stk3;\nint camSetEye(Stk3);\n\n'
              'void f(int *stk)\n{\n    camSetEye(*(Stk3 *)(((int)stk + 24)));\n}\n')

    def setUp(self):
        self.addCleanup(setattr, sh4abi, '_DEFS', sh4abi._DEFS)
        sh4abi._DEFS = {'camSetEye': ('camera.c', 'void', ['Vec3 *', 'int'])}

    def proto(self, text):
        out = sh4abi.abi_text(text, 'caller.c')
        self.assertIsNotNone(out)
        return [l for l in out.split('\n') if 'camSetEye(' in l and l.rstrip().endswith(';') and not l.startswith(' ')][0]

    def test_unknown_type(self):
        self.assertEqual(self.proto(self.CALLER), 'int camSetEye(void *, int);')

    def test_known_type(self):
        self.assertEqual(self.proto('typedef struct { float x, y, z; } Vec3;\n' + self.CALLER), 'int camSetEye(Vec3 *, int);')

    def test_struct_pointer(self):
        sh4abi._DEFS = {'camSetEye': ('camera.c', 'void', ['struct vec *', 'int'])}
        self.assertEqual(self.proto(self.CALLER), 'int camSetEye(struct vec *, int);')


if __name__ == '__main__':
    unittest.main()
