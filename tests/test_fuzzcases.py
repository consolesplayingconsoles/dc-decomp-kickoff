#!/usr/bin/env python3
"""fuzzcases.py (scripts/tools/6-agentic/fuzzcases.py): the mutation of a case, and the test that a kept case does not lean on registers the
function never set. No game data, no simulator run (the runs are stand-ins). Stdlib only.

    check.py      pure        mutate leaves the case it was given as it was, drops its "about", and is the same for the same seed
                  kinds       what it changes is an answer of a call, a poke at an address the original read, or r4-r7: nothing else
                  reads       it never pokes inside a function's code or literal pool, nor outside RAM
                  value       value() gives numbers, and a pointer it hands out is one of the scratch blocks it records
                  unset       a run that differs when the registers the function never set change is rejected; one that does not, kept
                  callargs    a call is compared only on the argument registers the function set for it (chg)
"""
import copy
import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools', '6-agentic'))
import fuzzcases  # noqa: E402

CASE = {'regs': {'r4': '00000001'}, 'calls': [{'r0': '00000002'}, {}], 'poke': {'0C100000': '01020304'}, 'about': 'seed'}
RUN = {'calls': [{}, {}], 'reads': [0x0C100000, 0x0C100010, 0x0C200000, 0x0C300000, 0x8C100020, 0x0E000000]}


class TestFuzzcases(unittest.TestCase):
    def setUp(self):
        saved = list(fuzzcases.CODE)
        self.addCleanup(lambda: fuzzcases.CODE.__setitem__(slice(None), saved))
        fuzzcases.CODE[:] = [(0x0C200000, 0x0C200100)]

    def test_pure(self):
        before = copy.deepcopy(CASE)
        a = fuzzcases.mutate(CASE, RUN, random.Random(5))
        self.assertEqual(CASE, before)
        self.assertNotIn('about', a)
        self.assertEqual(a, fuzzcases.mutate(CASE, RUN, random.Random(5)))

    def test_kinds_and_reads(self):
        for seed in range(300):
            c = fuzzcases.mutate(CASE, RUN, random.Random(seed))
            self.assertLessEqual(set(c), {'regs', 'calls', 'poke'})
            self.assertLessEqual(set(c.get('regs', {})), {'r4', 'r5', 'r6', 'r7'})
            for a in c.get('poke', {}):
                if a == '0C100000' and c['poke'][a] == CASE['poke'][a]:
                    continue                                   # the case's own poke
                at = int(a, 16) & 0x1FFFFFFF
                self.assertTrue(0x0C000000 <= at < 0x0D000000, a)
                self.assertFalse(0x0C200000 <= at < 0x0C200100, 'poked into code: ' + a)
            for cl in c.get('calls', []):
                self.assertLessEqual(set(cl), {'r0', 'fr0'})

    def test_value(self):
        rng = random.Random(1)
        ptrs = []
        for _ in range(500):
            v = fuzzcases.value(rng, ptrs)
            self.assertIsInstance(v, int)
            self.assertTrue(0 <= v <= 0xFFFFFFFF)
        self.assertTrue(ptrs)
        for p in ptrs:
            self.assertTrue(fuzzcases.SCRATCH <= p < fuzzcases.SCRATCH + 0x800 * 32)

    def test_is_code(self):
        self.assertTrue(fuzzcases.is_code(0x0C200000))
        self.assertTrue(fuzzcases.is_code(0x0C2000FF))
        self.assertFalse(fuzzcases.is_code(0x0C200100))
        self.assertFalse(fuzzcases.is_code(0x0C1FFFFF))

    def test_unset(self):
        first = {'out': {'r0': '5'}, 'writes': [], 'calls': []}
        dependent = lambda case: {'out': {'r0': case['regs'].get('r9', '0')}, 'writes': [], 'calls': []}
        independent = lambda case: {'out': {'r0': '5'}, 'writes': [], 'calls': []}
        self.assertTrue(fuzzcases.unset_dependent({}, first, dependent))
        self.assertFalse(fuzzcases.unset_dependent({}, first, independent))

    def test_callargs(self):
        call = lambda r5, chg: {'to': 'f', 'r4-r7': ['1', r5, '3', '4'], 'chg': chg, 'fr4-fr11': ['0'] * 8, 'fchg': [False] * 8}
        first = {'out': {'r0': '1'}, 'writes': [], 'calls': [call('2', [True, False, False, False])]}
        # a value left in r5 changes what the call shows, but r5 was not set for it: not a dependence
        run = lambda case: {'out': {'r0': '1'}, 'writes': [], 'calls': [call(case['calls'][0].get('r5', '2'), [True, False, False, False])]}
        self.assertFalse(fuzzcases.unset_dependent({}, first, run))
        # r4 is an argument the function set: when it differs, that is a dependence
        run2 = lambda case: {'out': {'r0': '1'}, 'writes': [], 'calls': [dict(call('2', [True, False, False, False]), **{'r4-r7': ['9', '2', '3', '4']})]}
        self.assertTrue(fuzzcases.unset_dependent({}, first, run2))


if __name__ == '__main__':
    unittest.main()
