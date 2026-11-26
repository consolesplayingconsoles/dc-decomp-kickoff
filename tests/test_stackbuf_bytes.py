#!/usr/bin/env python3
"""A word of a frame buffer passed to a call is compared on the bytes either side stored: a buffer of 9 bytes leaves three
of its third word as whatever the frame held. A byte only one side stored still has to agree. No game data. Stdlib only."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401
import sh4sim  # noqa: E402
import equiv  # noqa: E402

VIEW = [('0C000100', ['STACK'])]


def differ(a, ma, b, mb):
    return equiv.same_bufs([{'bufs': {'r4': [a]}, 'bufmask': {'r4': [ma]}}], [{'bufs': {'r4': [b]}, 'bufmask': {'r4': [mb]}}],
                           VIEW, VIEW)


class Bytes(unittest.TestCase):
    def test_bytes_nobody_stored_are_ignored(self):
        self.assertEqual(differ(0xF80000C3, 0x000000FF, 0xF90000C3, 0x000000FF), '')

    def test_a_stored_byte_must_agree(self):
        self.assertTrue(differ(0x000000C3, 0x000000FF, 0x000000C4, 0x000000FF))
        self.assertTrue(differ(0x000007C3, 0x0000FFFF, 0x000000C3, 0x000000FF))

    def test_memory_tracks_stored_bytes(self):
        m = sh4sim.Memory()
        top = m.stack[1] - 16
        m.write(top, 1, 5)
        self.assertEqual(m.byte_mask(top), 0x000000FF)
        m.write(top + 2, 2, 5)
        self.assertEqual(m.byte_mask(top), 0xFFFF00FF)
        m.pushed(top, 4)
        self.assertEqual(m.byte_mask(top), 0)


if __name__ == '__main__':
    unittest.main()
