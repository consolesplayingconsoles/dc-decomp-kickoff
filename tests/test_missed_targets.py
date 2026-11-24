#!/usr/bin/env python3
"""The addresses listed code calls, branches or tail-jumps to that no entry starts (scripts/tools/1-2-baseline/missed_funcs.py --targets).
No game data, no compiler. Stdlib only.

A function the analysis never listed is often reached only from listed code: a `bsr` or a branch to it, or a jump through a literal
pool word. The candidate list of missed_funcs.py (thousands of pointers and patterns in the gaps) buried them; this mode lists only those
targets, which a listed function plainly reaches.

    check.py      a temp repo: f1 (listed) calls an unlisted address with `bsr` and tail-jumps through a pool word to another, and the
                  listed g is reached from nowhere:
                    bsr      the bsr target is listed
                    jmp      the jump target read from the pool is listed
                    listed   g, a listed entry, is not
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
WORDS = [0x4F22, 0xB009, 0x0009, 0x4F26,     # 00 f1: sts.l pr; bsr 18; nop; lds.l pr
         0xD101, 0x412B, 0x0009, 0x0009,     # 08 mov.l @(10,pc),r1; jmp @r1; nop; (pad)
         0x0020, 0x0C01, 0x0009, 0x0009,     # 10 pool: 0c010020
         0x000B, 0xE001, 0x0009, 0x0009,     # 18 unlisted: rts; mov #1,r0
         0x000B, 0xE002,                     # 20 unlisted: rts; mov #2,r0
         0x000B, 0x0009]                     # 24 g
FUNCTIONS = 'F 0c010000 20 f1\nF 0c010024 4 g\n'


class TestMissedTargets(unittest.TestCase):
    def test_missed_targets(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(b''.join(struct.pack('<H', w) for w in WORDS))
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write(FUNCTIONS)
        out = subprocess.run([sys.executable, 'tools/1-2-baseline/missed_funcs.py', '--targets', '1ST_READ.BIN', '%08x' % BASE, 'functions.txt'],
                             cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout
        listed = {l.split()[0] for l in out.splitlines() if l[:1] in '0123456789abcdef' and len(l.split()[0]) == 8}
        bad = []
        if '0c010018' not in listed:
            bad.append('bsr: the bsr target 0c010018 is not listed')
        if '0c010020' not in listed:
            bad.append('jmp: the pool jump target 0c010020 is not listed')
        if '0c010024' in listed:
            bad.append('listed: g (0c010024), already an entry, is listed')
        if bad:
            self.fail('[ERROR] missed targets check failed:\n%s\noutput:\n%s' % ('\n'.join(bad), out))


if __name__ == '__main__':
    unittest.main()
