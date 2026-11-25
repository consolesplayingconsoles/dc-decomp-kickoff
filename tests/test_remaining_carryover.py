#!/usr/bin/env python3
"""What remaining.py keeps of its cached readings when the tools changed (scripts/tools/5-generated/remaining.py carry_over). No game
data, no compiler. Stdlib only.

When the tools change, the readings that said "readable" are kept, since a change nearly always widens what reads. A function that read
once and that every later run refused kept its "readable" for good: it was reported as "readable, no result" (not drawn) while the
runs' ledger said "cannot read" each time.

    check.py      cached readings from older tools and the ledger's latest outcome per function:
                    refused   readable in the cache, the ledger says cannot read: the ledger's reason is kept, with the same bytes key
                    passed    readable in the cache, the ledger says something else: still readable
                    unread    readable in the cache, no ledger entry: still readable
                    failed    cannot read in the cache: dropped (read again), or kept as it was in no-read mode
"""
import unittest
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
sys.path[:0] = [os.path.join(SKILL, 'scripts', 'tools', '5-generated'), os.path.join(SKILL, 'scripts', 'tools')]
import remaining  # noqa: E402

READ = {'refused': ['k1', 'readable'], 'passed': ['k2', 'readable'], 'unread': ['k3', 'readable'], 'failed': ['k4', 'cannot read: no T']}
LEDGER = {'refused': {'fn': 'refused', 'outcome': 'cannot read', 'detail': 'read r2 @8c0dd1b8'},
          'passed': {'fn': 'passed', 'outcome': 'DIFFERS', 'detail': 'case 1'}}


class TestRemainingCarryover(unittest.TestCase):
    def test_remaining_carryover(self):
        got = remaining.carry_over(READ, False, LEDGER)
        want = {'refused': ['k1', 'cannot read: read r2 @'], 'passed': ['k2', 'readable'], 'unread': ['k3', 'readable']}
        if got != want:
            self.fail('[ERROR] remaining carryover check failed: %r, expected %r' % (got, want))
        got = remaining.carry_over(READ, True, LEDGER)
        if got.get('failed') != ['k4', 'cannot read: no T'] or got.get('refused', [None, ''])[1] != 'cannot read: read r2 @':
            self.fail('[ERROR] remaining carryover check failed in no-read mode: %r' % got)


if __name__ == '__main__':
    unittest.main()
