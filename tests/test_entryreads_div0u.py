#!/usr/bin/env python3
"""The division set-up does not read the argument registers (scripts/tools/5-generated/gen_equiv/gen_core.py entry_reads_of). No game
data, no compiler. Stdlib only.

`div0u` names no operand and took the "not understood: reads every register" branch, so a routine with an inline division was taken to
read every argument and its callers were compared on their leftovers.

    check.py      div0u, then r4 copied to r0:
                    div       the entry reads r4 only
"""
import unittest
from unittest import mock
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')
GEN = os.path.join(TOOLS, '5-generated', 'gen_equiv')
sys.path[:0] = [GEN, os.path.join(GEN, '..'), TOOLS]


class TestEntryreadsDiv(unittest.TestCase):
    def setUp(self):
        self.addCleanup(os.chdir, os.getcwd())
        saved_path = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        environ = mock.patch.dict(os.environ)
        environ.start()
        self.addCleanup(environ.stop)
        snapshot = self._snapshot_modules()
        self.addCleanup(self._restore_modules, snapshot)

    @staticmethod
    def _snapshot_modules():
        tools = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts')
        modules = dict(sys.modules)
        state = {}
        for name, mod in modules.items():
            if (getattr(mod, '__file__', None) or '').startswith(tools):
                state[name] = dict(vars(mod))
        return modules, state

    @staticmethod
    def _restore_modules(snapshot):
        modules, state = snapshot
        for name in list(sys.modules):
            if name not in modules:
                del sys.modules[name]
        sys.modules.update(modules)
        for name, saved in state.items():
            vars(modules[name]).clear()
            vars(modules[name]).update(saved)

    def test_entryreads_div0u(self):
        os.chdir(tempfile.mkdtemp())             # gen_core reads the game's files when imported: stand-ins
        open('1ST_READ.BIN', 'wb').write(b'\x09\x00' * 64)
        open('BASE', 'w').write('8C010000\n')
        open('functions.txt', 'w').write('F 8c010000 128 stubfn\n')
        import gen_core
        ins = [('div0u', '', 0x8C010000), ('mov', 'r4,r0', 0x8C010002), ('rts', '', 0x8C010004), ('nop', '', 0x8C010006)]
        got = gen_core.entry_reads_of(ins, lambda n: frozenset())
        self.assertEqual(sorted(got or []), ['r4'], 'div: div0u reads no argument')


if __name__ == '__main__':
    unittest.main()
