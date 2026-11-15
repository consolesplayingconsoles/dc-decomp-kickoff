"""A simulated call can answer in the T flag (scripts/tools/sh4sim.py run). No game data, no compiler. Stdlib only.

A case answers each call the function makes outside its own range with a dict (`"calls": [{"r0": hex, "fr0": float, ...}]`).
A hand-written callee may answer in the T flag instead of, or as well as, a register. A call's `"t": 0|1` sets T on return; without
it T is left as the function had it.

    set       "t": 1 on a call whose function cleared T: T is 1 after the call
    clear     "t": 0 on a call whose function set T: T is 0 after the call
    absent    no "t": T is left as it was, set or clear
    masked    only the low bit counts: "t": 3 sets T
"""
import os
import struct
import sys
import tempfile
import unittest

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(SKILL, 'scripts', 'tools')
BASE = 0x0C010000
OUTSIDE = 0x0C0F0000

# <flag> / sts.l pr,@-r15 / mov.l @(pool),r1 / jsr @r1 / nop / movt r0 / lds.l @r15+,pr / rts / nop / nop / pool: the callee's address
CLEAR_T, SET_T = 0x0008, 0x0018


def code(first_op):
    words = [first_op, 0x4F22, 0xD103, 0x410B, 0x0009, 0x0029, 0x4F26, 0x000B, 0x0009, 0x0009]
    return struct.pack('<10H', *words) + struct.pack('<I', OUTSIDE)


class TestCallTFlag(unittest.TestCase):
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
        import sh4sim
        self.sh4sim = sh4sim

    @staticmethod
    def restore_modules(modules):
        for name in list(sys.modules):
            if name not in modules:
                del sys.modules[name]

    def t_after_call(self, first_op, answer):
        data = code(first_op)
        with open(os.path.join(self.tmp.name, '1ST_READ.BIN'), 'wb') as f:
            f.write(data)
        case = {'exe': '1ST_READ.BIN', 'base': '%08X' % BASE, 'entry': '%08X' % BASE, 'end': '%08X' % (BASE + len(data)),
                'calls': [answer]}
        result = self.sh4sim.run(case, self.tmp.name)
        self.assertFalse(result['error'], result['error'])
        return result['out']['r0']                       # movt r0 read T after the call

    def test_t_1_sets_the_flag(self):
        self.assertEqual(self.t_after_call(CLEAR_T, {'t': 1}), '00000001')

    def test_t_0_clears_the_flag(self):
        self.assertEqual(self.t_after_call(SET_T, {'t': 0}), '00000000')

    def test_without_t_the_flag_is_left_as_it_was(self):
        self.assertEqual(self.t_after_call(SET_T, {}), '00000001')
        self.assertEqual(self.t_after_call(CLEAR_T, {}), '00000000')

    def test_only_the_low_bit_counts(self):
        self.assertEqual(self.t_after_call(CLEAR_T, {'t': 3}), '00000001')


if __name__ == '__main__':
    unittest.main()
