#!/usr/bin/env python3
"""The `segmentset` rule of model_map (scripts/tools/3-assets/model_map.py segment_sets). No game data. Stdlib only.

A container file (a table of (offset, size) 32-bit pairs at the start, then the segments) can hold several models' lists of textures, one in each
model segment. The rule gives every model that lies in segment n the texture set the rule names, so those models look their texture numbers up in
the rows of that set and not in the file's own. These tests protect: only models inside the segment are marked; the others keep their set; a rule
for a file or a segment the disc does not have marks nothing.
"""
import os
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts", "tools", "3-assets"))
sys.path.insert(0, HERE)
import model_map  # noqa: E402
from test_recordparts import FakeDisc  # noqa: E402


def container(segments):
    """A container file: the table of (offset, size) pairs, then each segment's bytes where the table says."""
    head, body, at = bytearray(0x40), bytearray(), 0x40
    for i, size in enumerate(segments):
        struct.pack_into("<II", head, 8 * i, at, size)
        body += b"\0" * size
        at += size
    return bytes(head) + bytes(body)


def model(offset):
    return {"file": "A.BIN", "offset": offset, "texset": ""}


class TestSegmentSet(unittest.TestCase):
    def mark(self, models, rule=("segmentset", "A.BIN", "1", "segment1"), files=None):
        disc = FakeDisc(files if files is not None else {"A.BIN": container([0x100, 0x100, 0x100])})
        model_map.segment_sets([list(rule)], disc, models)
        return [m["texset"] for m in models]

    def test_models_inside_the_segment_take_its_set(self):
        self.assertEqual(self.mark([model(0x40), model(0x140), model(0x1ff), model(0x240)]), ["", "segment1", "segment1", ""],
                         "only the models of segment 1 (0x140 to 0x23f) are marked")

    def test_other_files_models_are_left_alone(self):
        other = {"file": "B.BIN", "offset": 0x150, "texset": ""}
        self.mark([other])
        self.assertEqual(other["texset"], "", "a model of another file keeps its set")

    def test_file_the_disc_lacks_marks_nothing(self):
        self.assertEqual(self.mark([model(0x150)], files={"B.BIN": b"\0" * 0x100}), [""], "no such file, no change")

    def test_segment_past_the_table_marks_nothing(self):
        self.assertEqual(self.mark([model(0x150)], rule=("segmentset", "A.BIN", "9", "x")), [""], "a segment the container lacks marks nothing")


if __name__ == "__main__":
    unittest.main()
