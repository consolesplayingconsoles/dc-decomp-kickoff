#!/usr/bin/env python3
"""Reading a C file's function definitions (scripts/tools/5-generated/sdk_place.py).
No game data, no compiler. Stdlib only.

    macro      a macro written over several lines with braces in it (`#define FOG_TABLE(base) do { ... } while (0)`) is not
               code: the reader took its `while (0)` and what followed for a function, and gave wrong bounds for the real
               function after it (Crazy Taxi, game_p.c)
    after      the functions after such a macro are found with their own bounds
    directive  a one-line directive with a brace (`#define OPEN {`) is not code either
    literal    a brace inside a string or a character constant does not open a block
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')
sys.path.insert(0, os.path.join(TOOLS, '5-generated'))
sys.path.insert(0, TOOLS)
import sdk_place  # noqa: E402

SRC = '''int first(int a)
{
    return a;
}

#define FOG_TABLE(base)                                  \\
    do {                                                 \\
        for (i = 0; i <= 128; i++) {                     \\
            t[i] = *(float *)(base);                     \\
        }                                                \\
    } while (0)

void second(void)
{
    FOG_TABLE(0x0C2B0000);
}

#define OPEN {
int third(int a)
{
    char c = '{';
    const char *s = "}} {";
    return a + c + s[0];
}
'''


class DefinitionsMacro(unittest.TestCase):
    def setUp(self):
        self.defs = sdk_place.definitions(SRC)
        self.names = [d[0] for d in self.defs]

    def test_macro(self):
        self.assertNotIn('while', self.names)
        self.assertEqual(self.names, ['first', 'second', 'third'])

    def test_after(self):
        name, start, end = self.defs[1]
        self.assertEqual(SRC[start:end], 'void second(void)\n{\n    FOG_TABLE(0x0C2B0000);\n}\n')

    def test_directive(self):
        name, start, end = self.defs[2]
        self.assertTrue(SRC[start:end].startswith('int third(int a)\n{'))

    def test_literal(self):
        name, start, end = self.defs[2]
        self.assertTrue(SRC[start:end].endswith('return a + c + s[0];\n}\n'))



class DefinitionsStructReturn(unittest.TestCase):
    """struct: a function that returns a pointer to a structure (`struct malloc_if *syMallocChangeIF(...)`) is a function:
    the reader took any text starting with `struct` for a declaration, the split left it out of the functions and copied
    it into every part of the file (Crazy Taxi, sdk_zf.c: three copies)"""

    def test_struct(self):
        src = ('struct malloc_if { int a; };\n\nstruct malloc_if *syMallocChangeIF(struct malloc_if *p)\n{\n    return p;\n}\n\n'
               'enum mode getMode(void)\n{\n    return 0;\n}\n')
        self.assertEqual([d[0] for d in sdk_place.definitions(src)], ['syMallocChangeIF', 'getMode'])


if __name__ == '__main__':
    unittest.main()
