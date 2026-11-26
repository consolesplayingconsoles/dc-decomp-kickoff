#!/usr/bin/env python3
"""retcheck: a prototype is not a use of the value. A file that only declares a function and calls it as a statement reads no
result; assigned, returned, compared or passed calls do. No game data. Stdlib only."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, '8-build'))
# the tool reads the game's files from the current folder when it is imported: stand-ins in a temporary one
_cwd = os.getcwd()
_tmp = tempfile.TemporaryDirectory()
os.chdir(_tmp.name)
with open('1ST_READ.BIN', 'wb') as _f:
    _f.write(b'\x09\x00' * 64)
with open('BASE', 'w') as _f:
    _f.write('8C010000\n')
with open('functions.txt', 'w') as _f:
    _f.write('F 8c010000 128 stubfn\n')
import toolpath  # noqa: E402,F401
import retcheck  # noqa: E402
os.chdir(_cwd)


class Prototype(unittest.TestCase):
    def test_declarations_and_statements_use_nothing(self):
        text = ('int f(int, int);\nextern int f(int a4);\nunsigned int f(void);\nchar *f(int);\n'
                'void g(void)\n{\n    f(1, 2);\n}\n')
        self.assertFalse(retcheck.used_value('f', text))

    def test_values_read(self):
        for line in ('    x = f(1);', '    return f(1);', '    return (f(1));', '    if (f(1)) {', '    h(f(1));',
                     '    x = y * f(1);'):
            self.assertTrue(retcheck.used_value('f', 'int f(int);\n' + line + '\n'), line)


if __name__ == '__main__':
    unittest.main()
