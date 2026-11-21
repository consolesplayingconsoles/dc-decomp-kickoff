"""A store queue's flush is an effect the checker compares (scripts/tools/sh4sim.py, pref). No game data, no compiler:
hand-assembled SH-4. Stdlib only.

The SH-4 sends a store queue's 32 bytes when the code runs pref on a store-queue address (0xE0000000-0xE3FFFFFF); on any other
address pref only warms the cache. Taken for a no-op, a helper that is pref @r4; rts, written in C as an empty function,
passed as Equivalent, and nothing sent through it went out.

    flush      pref on a store-queue address is recorded as a flush of its 32-byte block ('f', the block's address)
    cache      pref on a RAM address records nothing
    empty      the empty function and the original differ on that record: the checker's comparison fails
"""
import os
import struct
import sys
import tempfile
import unittest

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(SKILL, 'scripts', 'tools')
BASE = 0x0C010000
PREFETCH = struct.pack('<2H', 0x000B, 0x0483)          # rts / pref @r4 (in the delay slot): the original helper
EMPTY = struct.pack('<2H', 0x000B, 0x0009)             # rts / nop: the empty C's


class TestSqFlush(unittest.TestCase):
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
        import equiv
        self.sh4sim, self.equiv = sh4sim, equiv

    @staticmethod
    def restore_modules(modules):
        for name in list(sys.modules):
            if name not in modules:
                del sys.modules[name]

    def run_code(self, code, r4):
        with open(os.path.join(self.tmp.name, '1ST_READ.BIN'), 'wb') as f:
            f.write(code)
        case = {'exe': '1ST_READ.BIN', 'base': '%08X' % BASE, 'entry': '%08X' % BASE, 'end': '%08X' % (BASE + len(code)),
                'regs': {'r4': '%08X' % r4}}
        result = self.sh4sim.run(case, self.tmp.name)
        self.assertIsNone(result['error'])
        return result

    def test_flush(self):
        r = self.run_code(PREFETCH, 0xE0EA32A4)
        self.assertEqual(r['devices'], [['f', 'E0EA32A0', 32, '00000000000000000000000000000000000000000000000000000000000'
                                                               '00000']], 'the block of the address, 32 bytes')

    def test_cache(self):
        self.assertEqual(self.run_code(PREFETCH, 0x0C800000)['devices'], [], 'a cache prefetch is no effect')

    def test_empty(self):
        orig, empty = self.run_code(PREFETCH, 0xE0EA32A0), self.run_code(EMPTY, 0xE0EA32A0)
        good, diff = self.equiv.same(orig, empty, ['r0'], {})
        self.assertFalse(good, 'the empty helper differs from the original')
        self.assertIn('devices', diff)


if __name__ == '__main__':
    unittest.main()
