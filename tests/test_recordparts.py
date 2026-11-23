#!/usr/bin/env python3
"""The `recordparts` rule of model_map (scripts/tools/3-assets/model_map.py record_parts). No game data. Stdlib only.

A character whose parts, parent bones and bone offsets are a table of records inside its own model file (a segment of a container file: a table of
(offset, size) 32-bit pairs at the start, then the segments) is placed in bind pose and gets a skeleton, without the executable holding any table.
These tests protect: each bone's place is the sum of the offsets from the root down; the parent of a bone is the one its record names; a part is
found by its record's offset plus the segment's start; a model the map did not find leaves its bone in the skeleton with no part; a rule for a
file or a segment the disc does not have is skipped without stopping the others.
"""
import os
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts", "tools", "3-assets"))
import model_map  # noqa: E402

SEG = 0x40                       # where the one segment starts in the test file
RULE = ["recordparts", "Fighter", "form_0", "file=A.BIN", "segment=0", "count=3", "table=4", "stride=20", "model=0", "parent=4", "bone=8"]


class FakeDisc(object):
    def __init__(self, files):
        self.names = dict((i, (path, data)) for i, (path, data) in enumerate(sorted(files.items())))

    def files(self):
        return [(i, len(d), "/" + p) for i, (p, d) in self.names.items()]

    def read(self, lba, size):
        return self.names[lba][1][:size]


def container(records, count=None):
    """A container file of one segment: the table, then a segment whose header says how many records there are (word 3) and where they start
    (word 4, 0x20 into the segment); a record is a part offset in the segment, a parent (-1 for a root) and the bone offset (3 floats)."""
    body = bytearray(0x20)
    struct.pack_into("<II", body, 12, len(records) if count is None else count, 0x20)
    for model, parent, vec in records:
        body += struct.pack("<Ii3f", model, parent, *vec) + b"\0" * 12
    head = bytearray(SEG)
    struct.pack_into("<II", head, 0, SEG, len(body))
    return bytes(head) + bytes(body)


def part(offset):
    return {"file": "A.BIN", "offset": offset, "group": "", "sub": "", "name": "", "bytes": 4}


class TestRecordParts(unittest.TestCase):
    def run_rule(self, records, models, rule=RULE, files=None):
        disc = FakeDisc(files if files is not None else {"A.BIN": container(records)})
        return model_map.record_parts([rule], disc, models)

    def test_bone_place_is_the_sum_of_offsets_from_the_root(self):
        records = [(0x100, -1, (0, 10, 0)), (0x200, 0, (1, 2, 3)), (0x300, 1, (0, -4, 0))]
        placed, rigs, bones = self.run_rule(records, [part(SEG + 0x100), part(SEG + 0x200), part(SEG + 0x300)])
        move = dict((row[2], (row[8], row[12], row[16])) for row in placed)
        self.assertEqual(move["bone 0"], ("0.00000", "10.00000", "0.00000"), "the root is at its own offset")
        self.assertEqual(move["bone 1"], ("1.00000", "12.00000", "3.00000"), "a child is its parent's place plus its offset")
        self.assertEqual(move["bone 2"], ("1.00000", "8.00000", "3.00000"), "a grandchild adds both")

    def test_part_is_found_by_record_offset_plus_segment_start(self):
        models = [part(SEG + 0x100), part(0x100)]
        placed, rigs, bones = self.run_rule([(0x100, -1, (0, 0, 0)), (0, -1, (0, 0, 0)), (0, -1, (0, 0, 0))], models)
        self.assertEqual([(r[2], r[3], r[4]) for r in placed if r[2] == "bone 0"], [("bone 0", "A.BIN", "%x" % (SEG + 0x100))],
                         "the model at the segment's start plus the record's offset is the part, not the one at the bare offset")

    def test_parents_are_the_records_and_a_root_has_none(self):
        placed, rigs, bones = self.run_rule([(0, -1, (0, 0, 0)), (0, 0, (0, 0, 0)), (0, 1, (0, 0, 0))], [])
        self.assertEqual([b[3] for b in bones], ["", "0", "1"], "bone parents, a root's empty")
        self.assertEqual([r[0:3] for r in rigs], [["fighter", "bones", "Fighter"]], "one rig, named for the group")

    def test_model_the_map_did_not_find_leaves_a_bone_with_no_part(self):
        placed, rigs, bones = self.run_rule([(0x100, -1, (0, 0, 0)), (0x200, 0, (0, 0, 0)), (0x300, 1, (0, 0, 0))], [part(SEG + 0x200)])
        self.assertEqual([b[4] for b in bones], ["", "bone 1", ""], "only the bone whose model exists carries a part")
        self.assertEqual([r[2] for r in placed], ["bone 1"], "one part placed")

    def test_parts_take_the_rules_group_and_sub(self):
        models = [part(SEG + 0x100)]
        self.run_rule([(0x100, -1, (0, 0, 0)), (0, -1, (0, 0, 0)), (0, -1, (0, 0, 0))], models)
        self.assertEqual((models[0]["group"], models[0]["sub"]), ("Fighter", "form 0"), "the model is filed under the rule's group and sub")

    def test_rule_for_a_file_the_disc_lacks_is_skipped(self):
        out = self.run_rule([], [], files={"B.BIN": b"\0" * 64})
        self.assertEqual(out, ([], [], []), "no file, no rows, no error")

    def test_segment_past_the_table_is_skipped(self):
        rule = [x if x != "segment=0" else "segment=5" for x in RULE]
        out = self.run_rule([(0, -1, (0, 0, 0))] * 3, [], rule=rule)
        self.assertEqual(out, ([], [], []), "a segment the container does not have gives nothing")

    def test_records_past_the_segment_end_are_refused(self):
        out = self.run_rule([(0, -1, (0, 0, 0))], [], files={"A.BIN": container([(0, -1, (0, 0, 0))], count=50)})
        self.assertEqual(out, ([], [], []), "a count the segment cannot hold is not a table")


if __name__ == "__main__":
    unittest.main()
