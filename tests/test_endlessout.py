#!/usr/bin/env python3
"""An endless case is not compared on the result registers (scripts/tools/sim/equiv.py cut_endless, same). No game data. Stdlib only.

A case marked endless runs both sides to the step limit: the function never returned, so r0 and fr0 are whatever the last instruction
left there, and the compiled code, which takes a different number of instructions per pass of a loop, is cut somewhere else in the pass.
A function that waits on a callee (a loop that polls a word until it changes) holds the polled word in r0 at one cut and the loop's
compare constant at another: "original 00000000 / C FFFFFFFF" on a C that does what the original does on every pass. The calls both
sides made are still compared.

    check.py      result   two cut runs that differ only in r0 and fr0:                       agree
                  calls    two cut runs that made different calls in the same places:        differ
                  normal   two runs that returned (not cut) with different r0:               differ
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools', 'sim'))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools'))
import equiv  # noqa: E402


def run(r0, fr0='00000000', to='0C010000', error=None):
    call = {'to': to, 'r4-r7': ['00000000'] * 4, 'fr4-fr11': ['0'] * 8}
    return {'error': error, 'out': {'r0': r0, 'fr0': fr0}, 'calls': [call, dict(call)], 'writes': {}, 'devices': [], 'sr': None,
            'seq_used': False, 'xf': None}


class TestEndlessOut(unittest.TestCase):
    def compare(self, a, b):
        return equiv.same(a, b, ['r0', 'fr0'], {})[0]

    def test_result(self):
        a, b = equiv.cut_endless(run('00000000', '3F800000'), run('FFFFFFFF', '40000000'))
        self.assertTrue(self.compare(a, b))

    def test_calls(self):
        a, b = equiv.cut_endless(run('00000000', to='0C010000'), run('00000000', to='0C020000'))
        self.assertFalse(self.compare(a, b))

    def test_normal(self):
        self.assertFalse(self.compare(run('00000000'), run('FFFFFFFF')))


if __name__ == '__main__':
    unittest.main()
