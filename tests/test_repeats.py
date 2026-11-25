"""Functions whose original repeats one run of instructions (scripts/tools/7-reduction/repeats.py). No game data, no compiler.
Stdlib only.

    repeated_share   loop      a body of 12 instructions written four times, with other registers and constants: share 1.0, 4 copies
                     plain     12 different instructions twice over nothing: share 0 (a run must occur twice)
                     part      half the function repeated: a share near one half
                     short     a function shorter than two windows: 0
"""
import os
import sys
import unittest

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'tools')
BASE = 0x0C010000

# mov.l @(4,r4),r1 / add #3,r1 / mov.l r1,@(8,r4) / mov #5,r2 / mov.l r2,@(12,r4) / mov.l @(16,r4),r3 / add r3,r1 / dt r5 /
# mov.l r1,@(20,r4) / mov #7,r0 / mov.l r0,@(24,r4) / add #4,r4
BODY = [0x5141, 0x7103, 0x1412, 0xE205, 0x1423, 0x5344, 0x313C, 0x4510, 0x1415, 0xE007, 0x1406, 0x7404]
# the same shapes with other registers and constants
BODY2 = [0x5641, 0x7609, 0x1462, 0xE70B, 0x1473, 0x5144, 0x361C, 0x4210, 0x1465, 0xE00E, 0x1406, 0x7408]
OTHER = [0x0009, 0x6013, 0x2008, 0x8800, 0x6403, 0x3048, 0x4008, 0x4018, 0x6E03, 0x2EE8, 0x4E08, 0x6643]


class TestRepeats(unittest.TestCase):
    def setUp(self):
        saved = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved)
        sys.path.insert(0, os.path.join(TOOLS, '7-reduction'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import repeats
        self.r = repeats.repeated_share

    def test_loop(self):
        share, most = self.r(BODY + BODY2 + BODY + BODY2, BASE)
        self.assertEqual(share, 1.0)
        self.assertGreaterEqual(most, 4)

    def test_plain(self):
        share, most = self.r(OTHER + BODY, BASE)
        self.assertEqual(share, 0.0)

    def test_part(self):
        share, _ = self.r(BODY + BODY2 + OTHER + list(reversed(OTHER)), BASE)
        self.assertAlmostEqual(share, 0.5, delta=0.05)

    def test_short(self):
        self.assertEqual(self.r(BODY[:8], BASE), (0.0, 0))


if __name__ == '__main__':
    unittest.main()
