#!/usr/bin/env python3
"""A word equal to the image end, where the image ends at the BSS start (scripts/tools/1-2-baseline/symbolize.py end_is_bss). No game
data, no compiler. Stdlib only.

symbolize.py names every address word for the movable link: a target past the image is _bss+offset, so it follows the BSS. When the
image ends exactly where the BSS begins, the same value is both the end of a range inside the image and the start of the BSS. The
start-up code's section table (SHC: a range's end 12 bytes after its start) has both: a zero area inside the image ending there, and the
BSS starting there. The BSS moves by more than the image grows (it starts on a 0x1000 boundary), so named _bss the area's end ran past
the moved image and the start-up code cleared the gap: movecheck's check 2 differed at write 86,040 of 466,038 (Jet Set Radio).

    check.py      end       the word 12 bytes on is inside the image (the range ends here): the image end, not the BSS
                  start     the word 12 bytes on is past the image (the BSS end): the BSS start
                  alone     no word 12 bytes on: the image end
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools', '1-2-baseline'))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools'))
import symbolize  # noqa: E402

END = 0x0C300AE0


class TestSymbolizeImageEnd(unittest.TestCase):
    def test_symbolize_imageend(self):
        table_end = {0x0C102918: 0x8C2AFE80, 0x0C10292C: 0x8C2FEAE0, 0x0C102930: 0x8C2AFE80, 0x0C10293C: 0x8C300AE0}
        table_start = {0x0C2A6028: 0x8C300AE0, 0x0C2A6034: 0x8C35D720}
        got = {'end': symbolize.end_is_bss(table_end, 0x0C10293C, END),
               'start': symbolize.end_is_bss(table_start, 0x0C2A6028, END),
               'alone': symbolize.end_is_bss({0x0C000000: 0x8C300AE0}, 0x0C000000, END)}
        want = {'end': False, 'start': True, 'alone': False}
        if got != want:
            self.fail('[ERROR] symbolize imageend check failed: %r, expected %r' % (got, want))


if __name__ == '__main__':
    unittest.main()
