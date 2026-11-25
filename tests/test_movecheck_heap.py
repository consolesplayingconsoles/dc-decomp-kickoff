#!/usr/bin/env python3
"""Check 2 of movecheck and the heap that shrinks when the BSS moves (scripts/tools/1-2-baseline/movecheck.py writes_diff()). No game
data, no compiler, no simulator. Stdlib only.

The padded image's BSS moves up by bss_shift, while the top it may grow into (`fixed`) stays: the heap between the BSS end and that top
is smaller by exactly the move, and the game writes its size (Jet Set Radio: 0C800000 - 0C35D740 = 004A28C0 in the original, 004888C0
padded, 0x1A000 less) and values derived from it by a power of two (0x25146 against 0x24446, 0x1A000 / 0x20 less). Every other write
agreed (466,021 of 466,038), and check 2 reported DIFFERS. A 4-byte value smaller by the BSS move, or by the move divided by a power of
two, is the heap shrinking, not a difference.

    check.py      size      the heap size, smaller by the move: no difference
                  derived   a value smaller by the move / 32: no difference
                  other     a value smaller by an amount the move does not divide to a power of two: a difference
                  larger    a value larger by the move: a difference
                  none      without the move given (as before): a difference
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools', '1-2-baseline'))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools'))
import movecheck  # noqa: E402

MOVE = 0x1A000
new = lambda v: v                       # no address in these writes: the place is the same in both images


def w(addr, value):
    return ['%08X' % addr, 4, '%08X' % value]


class TestMovecheckHeap(unittest.TestCase):
    def diff(self, a, b, shrink=MOVE):
        wa, wb = [w(0x0C33E324, a)], [w(0x0C33E324, b)]
        return movecheck.writes_diff(wa, wb, new, shrink=shrink) if shrink else movecheck.writes_diff(wa, wb, new)

    def test_movecheck_heap(self):
        got = {'size': not self.diff(0x004A28C0, 0x004888C0), 'derived': not self.diff(0x00025146, 0x00024446),
               'other': not self.diff(0x00025146, 0x00024146), 'larger': not self.diff(0x004888C0, 0x004A28C0),
               'none': not self.diff(0x004A28C0, 0x004888C0, shrink=None)}
        want = {'size': True, 'derived': True, 'other': False, 'larger': False, 'none': False}
        if got != want:
            self.fail('[ERROR] movecheck heap check failed (True = passes): %r, expected %r' % (got, want))


if __name__ == '__main__':
    unittest.main()
