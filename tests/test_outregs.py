"""A routine that answers in registers other than r0 / fr0 is compared on the ones it names (scripts/tools/equiv.py returns and
scripts/tools/sh4sim.py run). No game data, no compiler. Stdlib only.

The checker compares a function on its result register, taken from its prototype: r0 for an integer, fr0 for a float, nothing for
void. A register-convention routine (inline assembly whose results stay in other registers) has results the prototype cannot name.
A comment `/* @out <fn> r9 fr0 */` in its C file adds those registers, after the usual one, and the simulator reports every general
and floating-point register so any of them can be compared.

    returns   plain      int gives r0, float gives fr0, void gives nothing
              named      @out adds the registers it names after the usual one
              void       @out on a void function gives the registers it names alone
              repeat     a register already there is not listed twice
              unknown    @out for a function the file does not define is ignored
    sim       all        the run reports r0-r15 and fr0-fr15
              values     a register the code set holds its value in that report
"""
import os
import struct
import sys
import tempfile
import unittest

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(SKILL, 'scripts', 'tools')
BASE = 0x0C010000

C_FILE = 'int whole(int a4)\n{\n    return a4;\n}\n\nfloat real(float a4)\n{\n    return a4;\n}\n\nvoid nothing(void)\n{\n}\n'


class TestOutRegisters(unittest.TestCase):
    def setUp(self):
        saved_path = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        modules = dict(sys.modules)
        self.addCleanup(self.restore_modules, modules)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(self.tmp.name)
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        sys.modules.pop('equiv', None)
        import equiv
        import sh4sim
        self.equiv, self.sh4sim = equiv, sh4sim

    @staticmethod
    def restore_modules(modules):
        for name in list(sys.modules):
            if name not in modules:
                del sys.modules[name]

    def returns(self, comment=''):
        path = os.path.join(self.tmp.name, 'f.c')
        with open(path, 'w') as f:
            f.write(C_FILE + comment)
        return self.equiv.returns(path)

    def test_plain_prototypes_give_the_usual_register(self):
        self.assertEqual(self.returns(), {'whole': ['r0'], 'real': ['fr0'], 'nothing': []})

    def test_out_adds_the_registers_it_names_after_the_usual_one(self):
        self.assertEqual(self.returns('/* @out whole r9 fr0 */\n')['whole'], ['r0', 'r9', 'fr0'])

    def test_out_on_a_void_function_gives_the_registers_alone(self):
        self.assertEqual(self.returns('/* @out nothing r9 fr3 */\n')['nothing'], ['r9', 'fr3'])

    def test_a_register_already_there_is_not_listed_twice(self):
        self.assertEqual(self.returns('/* @out whole r0 r9 */\n')['whole'], ['r0', 'r9'])

    def test_out_for_an_undefined_function_is_ignored(self):
        self.assertEqual(self.returns('/* @out missing r9 */\n'), {'whole': ['r0'], 'real': ['fr0'], 'nothing': []})

    def run_code(self, words):
        code = struct.pack('<%dH' % len(words), *words)
        with open(os.path.join(self.tmp.name, '1ST_READ.BIN'), 'wb') as f:
            f.write(code)
        case = {'exe': '1ST_READ.BIN', 'base': '%08X' % BASE, 'entry': '%08X' % BASE, 'end': '%08X' % (BASE + len(code))}
        result = self.sh4sim.run(case, self.tmp.name)
        self.assertFalse(result['error'], result['error'])
        return result['out']

    def test_the_run_reports_every_general_and_float_register(self):
        out = self.run_code([0x000B, 0x0009])                       # rts / nop
        for name in ['r%d' % i for i in range(16)] + ['fr%d' % i for i in range(16)]:
            self.assertIn(name, out)

    def test_a_register_the_code_set_holds_its_value(self):
        out = self.run_code([0xE905, 0xF39D, 0x000B, 0x0009])       # mov #5,r9 / fldi1 fr3 / rts / nop
        self.assertEqual(out['r9'], '00000005')
        self.assertEqual(out['fr3'], '3F800000')


if __name__ == '__main__':
    unittest.main()
