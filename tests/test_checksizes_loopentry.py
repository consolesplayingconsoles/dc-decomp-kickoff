#!/usr/bin/env python3
"""A loop's entry branch listed as its own function is merged with the loop (scripts/tools/1-2-baseline/checksizes.py --merge). No game
data, no compiler. Stdlib only.

SHC compiles `while (cond) body` as a branch to the test, the body, then the test, which branches back into the body. The analysis listed
the first instruction pair (`bra` to the test) as a 4-byte function, left the body unlisted and listed the test as a second function: the
first ends in a branch, so --merge saw nothing running off its end, and neither entry could be written as C (the test jumps back into
bytes no entry owns).

    check.py      a temp repo with two pairs of entries, each a 4-byte `bra` to the next entry with unlisted bytes between:
                    loop     the second entry branches back into those bytes: merged into one entry at the first address, size to the
                             end of the second, the first entry's name kept (callers name it)
                    thunk    the second entry never branches back (padding between): not merged
"""
import unittest
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
BASE = 0x0C010000
WORDS = [0xA006, 0x0009,                      # 00 loop_entry: bra 10
         0x6254, 0x6344, 0x3320, 0x8901,      # 04 body: compare two bytes, bt 10
         0x000B, 0xE000,                      # 0c rts, mov #0,r0
         0x4615, 0x8DF7, 0x76FF,              # 10 loop_test: cmp/pl r6; bt/s 04; add #-1,r6
         0xE001, 0x000B, 0x0009,              # 16 mov #1,r0; rts; nop
         0xA002, 0x0009,                      # 1c thunk: bra 24
         0x0009, 0x0009,                      # 20 padding
         0xE001, 0x000B, 0x0009, 0x0009]      # 24 target: mov #1,r0; rts; nop
FUNCTIONS = ('F 0c010000 4 loop_entry\nF 0c010010 12 loop_test\n'
             'F 0c01001c 4 thunk\nF 0c010024 6 target\n')


class TestChecksizesLoopEntry(unittest.TestCase):
    def test_checksizes_loopentry(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(b''.join(struct.pack('<H', w) for w in WORDS))
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write(FUNCTIONS)
        out = subprocess.run([sys.executable, 'tools/1-2-baseline/checksizes.py', '--merge', '--write'], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        got = open(os.path.join(tmp, 'functions.txt')).read().split('\n')
        bad = []
        if 'F 0c010000 28 loop_entry' not in got or any(l.endswith(' loop_test') for l in got):
            bad.append('loop: the entry branch and the loop test were not merged into `F 0c010000 28 loop_entry`')
        if 'F 0c01001c 4 thunk' not in got or 'F 0c010024 6 target' not in got:
            bad.append('thunk: a plain branch to the next function was merged')
        if bad:
            self.fail('[ERROR] checksizes loopentry check failed:\n%s\nfunctions.txt:\n%s\noutput:\n%s' % ('\n'.join(bad), '\n'.join(got), out))


if __name__ == '__main__':
    unittest.main()
