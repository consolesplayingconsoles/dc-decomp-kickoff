"""Backwards compatibility of the map tool's readers. Stdlib only.

Maps made by an older version must still read: what the readers found before, they still find. So an existing entry of
compat/golden.json may not change or disappear; the synthetic inputs (compat/emit.py) may only gain entries. Accepting new entries, or a
deliberate break, is `python3 tests/compat/update_golden.py [--breaking vX.Y]`, which records the break in golden.json (`breaking`): a
viewer must then have a reader from that version on (its own check reads this list).
"""
import json
import os
import subprocess
import sys
import unittest

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'compat')


def emitted():
    out = subprocess.run([sys.executable, os.path.join(DATA, 'emit.py')], stdout=subprocess.PIPE, check=True).stdout
    return json.loads(out.decode('utf-8'))


class TestCompat(unittest.TestCase):
    def test_readers_find_what_they_found_before(self):
        cases = emitted()
        with open(os.path.join(DATA, 'golden.json')) as f:
            old = json.load(f)['cases']
        removed = sorted(k for k in old if k not in cases)
        changed = sorted(k for k in old if k in cases and old[k] != cases[k])
        added = sorted(k for k in cases if k not in old)
        self.assertEqual(removed, [], 'readers that found something before no longer do (a deliberate break: update_golden.py --breaking <version>)')
        self.assertEqual(changed, [], 'a reader\'s output changed, which breaks maps made by earlier versions: fix the reader, or update_golden.py --breaking <version>')
        self.assertEqual(added, [], 'new entries are not in golden.json yet: run tests/compat/update_golden.py')


if __name__ == '__main__':
    unittest.main()
