#!/usr/bin/env python3
"""How check 2 of movecheck compares the writes of the original and of the padded image (scripts/tools/1-2-baseline/movecheck.py
writes_diff()). No game data, no compiler, no simulator. Stdlib only.

The padded image has an address value at its place: a 4-byte write of an address word differs from the original's by the pad
(new(value)), and is the same write. A table of addresses copied a byte at a time (memcpy of a pointer table) writes the same
word as four byte writes, so each byte differs from the original's and the run was reported DIFFERS (Power Stone 2: bytes AC 3D 1A
0C at 0C2AE8F4 in the original, 2C 60 1B 0C at the padded address: 0C1A3DAC and its place 0C1B602C). A run of four byte writes to
the four bytes of an aligned word, in ascending order, in both images, is compared as the word.

The change only accepts more, never less: whatever the old comparison passed, the new one passes (a run of equal bytes is an equal word).

    check.py      word      four byte writes of an address word, the padded one's at its place:      no difference
                  plain     the same word as one 4-byte write (as before):                           no difference
                  value     a byte run whose word is neither the original's nor its place:           a difference, at the run's first write
                  place     a byte run written somewhere else than the original's place:             a difference
                  order     bytes in descending order, or unaligned, or with another write between:   compared one by one, as before
                  partial   three bytes then another size (not a run of four):                        compared one by one, as before
                  size      a write of another size than the original's:                              a difference
                  limit     at most 8 differences are returned, the first ones
                  superset  random write lists: every list the old comparison passed, the new one passes too
"""
import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools', '1-2-baseline'))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools'))
import movecheck  # noqa: E402

LO, HI, PAD = 0x0C010000, 0x0C100000, 32
GSTART = [0x0C010000, 0x0C020000, 0x0C030000, 0x0C040000]       # three pads in front of the last group
new = movecheck.mapper(GSTART, PAD, HI, LO, HI)


def w(addr, size, value):
    return ['%08X' % addr, size, '%0*X' % (size * 2, value)]


def bytes_of(addr, value):
    """the four byte writes of a little-endian word, at ascending addresses"""
    return [w(addr + i, 1, (value >> (8 * i)) & 0xFF) for i in range(4)]


def old_diff(wa, wb):
    """check 2 as it was: one write against one write"""
    out = []
    for k, (x, y) in enumerate(zip(wa, wb)):
        ax, s, av = int(x[0], 16), x[1], int(x[2], 16)
        bx, s2, bv = int(y[0], 16), y[1], int(y[2], 16)
        if bx != new(ax) or s != s2 or not (bv == av or (s == 4 and bv == new(av))):
            out.append((k, x, y))
            if len(out) >= 8:
                break
    return out


class TestWritesDiff(unittest.TestCase):
    def diff(self, wa, wb):
        return movecheck.writes_diff(wa, wb, new)

    def test_word(self):
        a = 0x0C020010
        v = 0x0C03A100                                           # an address in the last group: it moved by three pads
        wa, wb = bytes_of(a, v), bytes_of(new(a), new(v))
        self.assertNotEqual(new(v), v)
        self.assertTrue(old_diff(wa, wb), 'the old comparison reported this run')
        self.assertEqual(self.diff(wa, wb), [])

    def test_plain(self):
        a, v = 0x0C020010, 0x0C03A100
        wa, wb = [w(a, 4, v)], [w(new(a), 4, new(v))]
        self.assertEqual(old_diff(wa, wb), [])
        self.assertEqual(self.diff(wa, wb), [])

    def test_value(self):
        a, v = 0x0C020010, 0x0C03A100
        wa, wb = bytes_of(a, v), bytes_of(new(a), new(v) + 1)    # neither v nor its place
        d = self.diff(wa, wb)
        self.assertEqual([k for k, x, y in d], [0])

    def test_value_unrelocated_is_equal(self):
        a, v = 0x0C020010, 0x00001234                            # a number: written as it is
        wa, wb = bytes_of(a, v), bytes_of(new(a), v)
        self.assertEqual(self.diff(wa, wb), [])

    def test_place(self):
        a, v = 0x0C020010, 0x0C03A100
        wa, wb = bytes_of(a, v), bytes_of(a, new(v))             # the padded image wrote at the original's address
        self.assertTrue(self.diff(wa, wb))

    def test_order(self):
        a, v = 0x0C020010, 0x0C03A100
        wa = list(reversed(bytes_of(a, v)))                      # descending: not a run
        wb = list(reversed(bytes_of(new(a), new(v))))
        self.assertEqual(self.diff(wa, wb), old_diff(wa, wb))
        self.assertTrue(self.diff(wa, wb))
        un = bytes_of(a + 1, v)                                  # unaligned start: not a word
        self.assertEqual(self.diff(un, bytes_of(new(a + 1), new(v))), old_diff(un, bytes_of(new(a + 1), new(v))))
        mid = bytes_of(a, v)
        mid.insert(2, w(0x0C020100, 4, 7))                       # another write between
        pb = bytes_of(new(a), new(v))
        pb.insert(2, w(new(0x0C020100), 4, 7))
        self.assertEqual(self.diff(mid, pb), old_diff(mid, pb))

    def test_partial(self):
        a, v = 0x0C020010, 0x0C03A100
        wa = bytes_of(a, v)[:3] + [w(a + 3, 2, 0x0C03)]
        wb = bytes_of(new(a), new(v))[:3] + [w(new(a) + 3, 2, 0x0C03)]
        self.assertEqual(self.diff(wa, wb), old_diff(wa, wb))
        wb2 = bytes_of(new(a), new(v))                           # the padded one has the four bytes, the original three and a half-word
        self.assertEqual(self.diff(wa, wb2), old_diff(wa, wb2))

    def test_size(self):
        a = 0x0C020010
        self.assertTrue(self.diff([w(a, 2, 5)], [w(new(a), 4, 5)]))

    def test_limit(self):
        wa = [w(0x0C020000 + 4 * k, 4, k) for k in range(20)]
        wb = [w(new(0x0C020000 + 4 * k), 4, k + 100) for k in range(20)]
        d = self.diff(wa, wb)
        self.assertEqual(len(d), 8)
        self.assertEqual([k for k, x, y in d], list(range(8)))

    def test_lists_of_different_length(self):
        a, v = 0x0C020010, 0x0C03A100
        wa = bytes_of(a, v) + [w(a + 8, 4, 1)]
        wb = bytes_of(new(a), new(v))                            # the original went on: not a difference here (the caller says so)
        self.assertEqual(self.diff(wa, wb), [])

    def test_superset(self):
        rng = random.Random(7)
        addrs = [0x0C010100, 0x0C020100, 0x0C030100, 0x0C040100, 0x0C050100]
        vals = [0, 1, 0xFF, 0x0C010800, 0x0C030800, 0x0C050800, 0x12345678, 0xFFFFFFFF]
        checked = passed = 0
        for _ in range(4000):
            wa, wb = [], []
            for _ in range(rng.randint(1, 6)):
                a = rng.choice(addrs) + 4 * rng.randint(0, 3)
                v = rng.choice(vals)
                kind = rng.randint(0, 4)
                if kind == 0:                                    # a word, written right
                    wa.append(w(a, 4, v)); wb.append(w(new(a), 4, new(v)))
                elif kind == 1:                                  # a word, written as it is (a number)
                    wa.append(w(a, 4, v)); wb.append(w(new(a), 4, v))
                elif kind == 2:                                  # four bytes, right
                    wa += bytes_of(a, v); wb += bytes_of(new(a), new(v))
                elif kind == 3:                                  # four bytes, as they are
                    wa += bytes_of(a, v); wb += bytes_of(new(a), v)
                else:                                            # anything: a wrong value, address or size
                    s = rng.choice([1, 2, 4])
                    wa.append(w(a, s, v & ((1 << (8 * s)) - 1)))
                    wb.append(w(rng.choice([new(a), a, new(a) + 1]), rng.choice([s, s, 4 if s != 4 else 2]),
                                rng.choice([v, new(v)]) & ((1 << (8 * s)) - 1)))
            checked += 1
            if not old_diff(wa, wb):
                passed += 1
                self.assertEqual(self.diff(wa, wb), [], '%s / %s' % (wa, wb))
        self.assertGreater(passed, 300, 'the property was exercised on lists the old comparison passed: %d of %d' % (passed, checked))


if __name__ == '__main__':
    unittest.main()
