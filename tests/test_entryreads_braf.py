#!/usr/bin/env python3
"""A function that dispatches through a `braf` table reads only what its cases read (scripts/tools/5-generated/gen_equiv/gen_core.py
entry_reads_of). No game data, no compiler. Stdlib only.

With the targets unknown the reads pass took a `braf` to reach any instruction, the table's own words decoded as code among them, so
the function was taken to read every argument register and its callers were compared on their leftovers.

    check.py      a two-entry table behind a bounds check; the table words decode as instructions that name r5 and r6:
                    cases     the entry reads r4 and fr4, nothing else
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


class TestEntryreadsBraf(unittest.TestCase):
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

    def test_entryreads_braf(self):
        os.chdir(tempfile.mkdtemp())             # gen_core reads the game's files when imported: stand-ins
        base = 0x8C010000
        table = base + 14                        # the table follows the braf's delay slot
        words = [0x0009] * 7 + [0x0000, 0x0004] + [0x0009] * 16          # offsets from the braf + 4 (= the table): cases at +0 and +4
        open('1ST_READ.BIN', 'wb').write(b''.join(bytes((w & 0xFF, w >> 8)) for w in words))
        open('BASE', 'w').write('%08X\n' % base)
        open('functions.txt', 'w').write('F 8c010000 50 stubfn\n')
        import gen_core
        pc = lambda k: base + 2 * k
        ins = [('mov', '#2,r1', pc(0)), ('cmp/hs', 'r1,r4', pc(1)), ('bt', '0x%x' % pc(13), pc(2)), ('shll', 'r4', pc(3)),
               ('mova', '@(0x%x,pc),r0' % table, pc(4)), ('mov.w', '@(r0,r4),r0', pc(5)), ('braf', 'r0', pc(6))]
        base_ = pc(6) + 4                        # = pc(8): the delay slot is pc(7), the table starts at pc(7)
        ins = ins[:4] + [('mova', '@(0x%x,pc),r0' % pc(8), pc(4))] + ins[5:]
        ins += [('nop', '', pc(7)), ('mov.l', 'r5,@r6', pc(8)), ('mov.l', 'r7,@r5', pc(9)),      # pc 8, 9: the table, decoded as code
                ('rts', '', pc(10)), ('fldi1', 'fr0', pc(11)), ('fmov', 'fr4,fr0', pc(12)), ('rts', '', pc(13)), ('nop', '', pc(14))]
        words = [0x0009] * 8 + [0x0000, 0x0004] + [0x0009] * 15          # base_ = pc(8)... offsets: pc(10) and pc(12)
        gen_core.BIN = b''.join(bytes((w & 0xFF, w >> 8)) for w in words[:8]) + bytes((pc(10) - base_ & 0xFF, 0, pc(12) - base_ & 0xFF, 0))
        gen_core.BASE = base
        got = gen_core.entry_reads_of(ins, lambda n: frozenset())
        self.assertEqual(sorted(got or []), ['fr4', 'r4'], 'cases: a braf table')


if __name__ == '__main__':
    unittest.main()
