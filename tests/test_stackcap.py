#!/usr/bin/env python3
"""The stack words compared at a call to a callee that takes one padded structure (scripts/tools/sim/equiv.py compared_arity). No game data, no
compiler. Stdlib only.

The generator pads a callee that takes only stack words to four (`Stk4 s`) so the structure goes on the stack, and the checker compared a call
on all four words: the two its original code never reads are the caller's frame leftovers, different in the original and in the C. The words
compared are now at most the ones the original code reads, when that can be told.

    check.py      a definition `(0 registers, 0 floats, 4 words)`, the original reads:
                    two       2 words: compared on two
                    unknown   0 (it cannot be told): the four are kept
                    all       4 words: compared on four
"""
import unittest
from unittest import mock
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
TOOLS = os.path.join(SKILL, 'scripts', 'tools')


class TestStackCap(unittest.TestCase):
    def setUp(self):
        saved_path = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        modules = dict(sys.modules)
        self.addCleanup(lambda: [sys.modules.pop(n) for n in list(sys.modules) if n not in modules])
        sys.path[:0] = [os.path.join(TOOLS, 'sim'), TOOLS]
        import equiv
        self.equiv = equiv

    def compared(self, reads):
        equiv = self.equiv
        with mock.patch.object(equiv, 'definitions', return_value={'callee': (0, 0, 4)}), \
                mock.patch.object(equiv, 'prototypes', return_value={}), \
                mock.patch.object(equiv, 'stack_args', return_value={}), \
                mock.patch.object(equiv, 'used_definitions', return_value={'callee': (0, 0, 4)}), \
                mock.patch.object(equiv, '_orig_stack_words', return_value=reads):
            return equiv.compared_arity('x.c', {'callee': 0x8C000100})[1].get(0x0C000100)

    def test_stackcap(self):
        got = {'two': self.compared(2), 'unknown': self.compared(0), 'all': self.compared(4)}
        if got != {'two': 2, 'unknown': 4, 'all': 4}:
            self.fail('[ERROR] stackcap check failed: words compared %r, expected two 2, unknown 4, all 4' % got)


if __name__ == '__main__':
    unittest.main()
