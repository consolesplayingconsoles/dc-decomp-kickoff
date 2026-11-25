#!/usr/bin/env python3
"""The second pass for the functions whose draw timed out (scripts/tools/5-generated/gen_equiv/secondpass.py). No game data, no compiler.
Stdlib only.

A draw has a time limit, max(60, size/8) s times GEN_TIME_FACTOR. A function whose draw costs more CPU than that is reported "not drawn:
Timeout" though nothing is wrong with it: a small function with big call answers took 395 s of CPU against the 60 s floor (a quiet
machine does not help: it is CPU time). The limit stays short for the first pass, so one function that really hangs cannot hold a run,
and the run says how to try the timeouts again: alone, with a longer limit, smallest first. Only the functions that timed out: a function
the original never finishes on, or one the reader skips, would not change with more time.

    check.py      hint(not-drawn records, size of each): the lines the run prints at its end
                    timeouts   only the records whose reason is Timeout are named, smallest first, with the command
                    others     no other reason is named; with no timeout the hint is empty
                    limit      the command's size limit is the largest of the named functions, and GEN_TIME_FACTOR is 8 and --jobs 1
                    wired      gen_equiv's own run (__main__.py) collects the timeouts and prints the hint
"""
import unittest
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(os.path.dirname(HERE), 'scripts', 'tools', '5-generated', 'gen_equiv')
sys.path.insert(0, GEN)
sys.path.insert(0, os.path.join(GEN, '..'))
sys.path.insert(0, os.path.join(GEN, '..', '..'))
import secondpass  # noqa: E402

SIZES = {'big': 600, 'small': 80, 'mid': 300, 'loop': 90, 'nofr0': 120}
RECS = [('skip', 'big', 'Timeout'), ('skip', 'loop', 'Skip the original does not finish on the cases'), ('skip', 'small', 'Timeout'),
        ('skip', 'nofr0', 'Skip no fr0'), ('skip', 'mid', 'Timeout')]


class TestSecondPass(unittest.TestCase):
    def test_gen_secondpass(self):
        bad = []
        text = '\n'.join(secondpass.hint(RECS, SIZES.get))
        names = [w for w in text.split() if w in SIZES]
        if names != ['small', 'mid', 'big']:
            bad.append('timeouts: named %r, expected small, mid, big (smallest first, only the three that timed out): %s' % (names, text))
        if 'loop' in text.split() or 'nofr0' in text.split():
            bad.append('others: a function that did not time out is named: %s' % text)
        if secondpass.hint([('skip', 'loop', 'Skip the original does not finish on the cases')], SIZES.get):
            bad.append('others: a hint was printed with no timeout in the run')
        if 'GEN_TIME_FACTOR=8' not in text or '--jobs 1' not in text or ' 600 ' not in ' ' + text + ' ':
            bad.append('limit: expected GEN_TIME_FACTOR=8, --jobs 1 and the size limit 600 in the command: %s' % text)
        src = open(os.path.join(GEN, '__main__.py'), encoding='utf-8', errors='replace').read()
        if 'secondpass.hint' not in src or 'TIMED' not in src:
            bad.append('wired: __main__.py does not collect the timeouts and print the hint')
        if bad:
            self.fail('[ERROR] gen secondpass check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
