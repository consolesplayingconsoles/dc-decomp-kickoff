#!/usr/bin/env python3
"""The stack words the ORIGINAL pushes for a call are compared whatever the caller's C prototype says (scripts/tools/sim/equiv.py same/callview,
the sim's per-call `stackpush`). No game data, no compiler. Stdlib only.

The words compared at a call were capped at the caller's prototype (compared_arity): a call to a printf-style callee declared with five
integers while the original pushed two words past r4-r7 proved EQUIVALENT with one of them missing (Power Stone 2 FUN_0c187cac).

    check.py      an original caller that pushes two words and calls a callee declared with one stack word (five integers):
                    short     the C passes one word fewer: DIFFERS
                    full      the C passes both words: EQUIVALENT
"""
import unittest
import os
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
BASE = 0x0C010000
W = lambda ws: b''.join(struct.pack('<H', w) for w in ws)
# sts.l pr / mov #1,r2 / mov #2,r3 / push r2 / push r3 / bsr BASE+0x100 / mov #4,r4 / add #8,r15 / lds.l pr / rts / nop
CALLER = [0x4F22, 0xE201, 0xE302, 0x2F26, 0x2F36, 0xB07F, 0xE404, 0x7F08, 0x4F26, 0x000B, 0x0009]
CALLEE = BASE + 0x100


class TestStackWordsPastPrototype(unittest.TestCase):
    def setUp(self):
        saved_path = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        modules = dict(sys.modules)
        self.addCleanup(lambda: [sys.modules.pop(n) for n in list(sys.modules) if n not in modules])
        sys.path[:0] = [os.path.join(SKILL, 'scripts', 'tools', 'sim'), os.path.join(SKILL, 'scripts', 'tools')]
        import equiv
        import sh4sim
        self.equiv, self.sim = equiv, sh4sim

    def test_stackwords_past_prototype(self):
        equiv, sim = self.equiv, self.sim
        tmp = tempfile.mkdtemp()
        code = W(CALLER)
        open(os.path.join(tmp, 'x.bin'), 'wb').write(code)
        case = {'exe': 'x.bin', 'base': '%08X' % BASE, 'entry': '%08X' % BASE, 'end': '%08X' % (BASE + len(code)), 'regs': {}}
        orig = sim.run(case, tmp)
        calls = orig['calls']
        if len(calls) != 1:
            self.fail('[ERROR] stackwords check failed: the original made %d calls, expected 1 (%r)' % (len(calls), orig['error']))

        def verdict(mine_words):
            mine = dict(orig, calls=[dict(calls[0], stackw=list(mine_words), stackchg=[True] * len(mine_words), stackpush=[True] * len(mine_words))])
            equiv.STACKN.clear()
            equiv.STACKN[CALLEE] = 1                   # the prototype: five integers, one stack word
            return equiv.same(orig, mine, ['r0'], {}, {CALLEE: (4, 0)})[0]
        w = calls[0]['stackw']
        short = verdict([w[0]] + ['00000000'] + w[2:])
        full = verdict(w)
        if (short, full) != (False, True):
            self.fail('[ERROR] stackwords check failed: a call one pushed word short gave %r (expected DIFFERS), all words %r (expected EQUIVALENT)'
                      % (short, full))


if __name__ == '__main__':
    unittest.main()
