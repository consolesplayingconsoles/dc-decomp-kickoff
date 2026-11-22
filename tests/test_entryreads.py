#!/usr/bin/env python3
"""Which argument registers a callee reads, as a set (scripts/tools/5-generated/gen_equiv/gen_core.py entry_reads_of), and the call
comparison that uses it (scripts/tools/sim/equiv.py callview). No game data, no compiler. Stdlib only.

callee_arity counts up to the highest register a function reads: cpuShotRange (Virtua Tennis) reads fr6-fr10 after a call, counts 7
floats and so takes in fr4 and fr5; cpuSglAimScore's generated C names fr4 and fr5 only to pass them on, and its caller
cpuSglPickLv07 was compared on a leftover fr5 (1.0 in the original, 5 in the C) and dropped from 100%.

    check.py      instruction lists as gen_core reads them:
                    passon    fr4/fr5 untouched up to a call (target loaded 9 instructions before the jsr) to a callee that reads fr6
                              only: the function reads fr6, not fr4 or fr5
                    clobber   a float read after a call is not read at the entry (the call writes fr0-fr11)
                    unknown   a jmp out of the function (a tail call) or frchg: not known (None), nothing is masked
                    masked    callview compares a call only on the registers its callee's original reads; the rest show as *
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


class TestEntryreads(unittest.TestCase):
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

    def test_entryreads(self):
        os.chdir(tempfile.mkdtemp())             # gen_core reads the game's files when imported: stand-ins
        open('1ST_READ.BIN', 'wb').write(b'\x09\x00' * 64)
        open('BASE', 'w').write('8C010000\n')
        open('functions.txt', 'w').write('F 8c010000 128 stubfn\n')
        import gen_core
        bad = []
        if not hasattr(gen_core, 'entry_reads_of'):
            self.fail('[ERROR] entryreads check failed:\ngen_core has no entry_reads_of')
        pc = [0x8C000000 + 2 * k for k in range(40)]
        a = [('mov.l', '@(0x8c000060,pc),r3 ; =8c000100 calleeB', pc[0])]
        a += [('mov', '#%d,r1' % k, pc[1 + k]) for k in range(8)]                 # 8 instructions between the load and the jsr
        a += [('mov', 'r4,r14', pc[9]), ('jsr', '@r3', pc[10]), ('nop', '', pc[11]), ('fmov', 'fr0,fr1', pc[12]),
              ('rts', '', pc[13]), ('nop', '', pc[14])]
        reads = {'calleeB': frozenset(['fr6'])}
        got = gen_core.entry_reads_of(a, lambda n: reads.get(n))
        if got is None or 'fr4' in got or 'fr5' in got or 'fr6' not in got or 'r4' not in got:
            bad.append('passon: entry reads %s, want r4 and fr6, not fr4/fr5' % (sorted(got) if got is not None else None))
        b = [('mov.l', '@(0x8c000060,pc),r3 ; =8c000100 calleeC', pc[0]), ('jsr', '@r3', pc[1]), ('nop', '', pc[2]),
             ('fmov', 'fr4,fr0', pc[3]), ('rts', '', pc[4]), ('nop', '', pc[5])]
        got = gen_core.entry_reads_of(b, lambda n: frozenset())
        if got is None or 'fr4' in got:
            bad.append('clobber: fr4 read after a call counts as read at the entry (%s)' % (sorted(got) if got is not None else None))
        c = [('mov.l', '@(0x8c000060,pc),r3 ; =8c000100 calleeD', pc[0]), ('jmp', '@r3', pc[1]), ('nop', '', pc[2])]
        d = [('frchg', '', pc[0]), ('fmov', 'fr4,fr0', pc[1]), ('rts', '', pc[2]), ('frchg', '', pc[3])]
        for name, ins in (('tail call', c), ('frchg', d)):
            if gen_core.entry_reads_of(ins, lambda n: frozenset()) is not None:
                bad.append('unknown: a %s gives a set, not None' % name)
        import equiv
        equiv._READS[0x0C000100] = (frozenset([4]), frozenset([6]))
        v = equiv.callview('0C000100', ['00000001', '00000002'], ['3F800000', '40000000', '40400000'], {0x0C000100: (2, 3)})
        if v[1][:2] != ['00000001', '*'] or v[2] != ['*', '*', '40400000']:
            bad.append('masked: callview gives %s %s, want r4 and fr6 only' % (v[1], v[2]))
        # declared `f(void)` in the file (arity 0), the callee's code reads r4 and r5, the original set r5 for the call (chg): compared on
        # r5, so a C side that left r5 as it was differs; r4, which the original did not set either, is a leftover on both sides
        equiv._READS[0x0C000300] = (frozenset([4, 5]), frozenset())
        equiv._READS_SURE[0x0C000300] = frozenset([4, 5])
        vo = equiv.callview('0C000300', ['00000007', '0DFF1000', '0', '0'], [], {0x0C000300: (0, 0)}, chg=[False, True, False, False])
        vc = equiv.callview('0C000300', ['00000007', '0C123456', '0', '0'], [], {0x0C000300: (0, 0)}, chg=[False, True, False, False])
        if vo[1] != ['*', 'STACK'] or vc[1] != ['*', '0C123456']:
            bad.append('undeclared: a register the original set and the callee reads is compared though the file declares f(void): %s / %s' % (vo[1], vc[1]))
        equiv._READS_SURE[0x0C000400] = frozenset([4])          # the callee reads r5 only through a call via a pointer: not for certain
        equiv._READS[0x0C000400] = (frozenset([4, 5]), frozenset())
        vp = equiv.callview('0C000400', ['00000007', '0DFF1000', '0', '0'], [], {0x0C000400: (1, 0)}, chg=[True, True, False, False])
        if vp[1] != ['00000007']:
            bad.append('undeclared: a register the callee reads only through a pointer call is not compared beyond the declaration, got %s' % (vp[1],))
        vn = equiv.callview('0C000300', ['00000007', '0DFF1000', '0', '0'], [], {0x0C000300: (0, 0)}, chg=[False, False, False, False])
        if vn[1] != []:
            bad.append('undeclared: with nothing set by the original the declared arity stands, got %s' % (vn[1],))
        # a call through a pointer with r6 untouched: read for the generator (the safe side), not for certain (entry_reads_sure's rule)
        ind = [('mov.l', '@(12,r2),r3', 0x8C000000), ('jsr', '@r3', 0x8C000002), ('mov', 'r4,r4', 0x8C000004), ('rts', '', 0x8C000006), ('nop', '', 0x8C000008)]
        full = gen_core.entry_reads_of(ind)
        gen_core._SURE = True
        try:
            sure = gen_core.entry_reads_of(ind)
        finally:
            gen_core._SURE = False
        if full is None or 'r6' not in full or sure is None or 'r6' in sure or 'r4' not in sure:
            bad.append('sure: a call through a pointer reads r6 for the generator (%s) and not for certain (%s); r4, read by the code itself, stays' % (sorted(full or []), sorted(sure or [])))
        equiv._READS[0x0C000200] = None
        v = equiv.callview('0C000200', ['00000001', '00000002'], ['3F800000'], {0x0C000200: (2, 1)})
        if v[1][:2] != ['00000001', '00000002'] or v[2] != ['3F800000']:
            bad.append('masked: an unknown callee lost registers (%s %s)' % (v[1], v[2]))
        if bad:
            self.fail('[ERROR] entryreads check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
