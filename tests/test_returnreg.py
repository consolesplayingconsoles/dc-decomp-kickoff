#!/usr/bin/env python3
"""The register a function returns in decides which declarations the generator may try (scripts/tools/5-generated/gen_equiv/gen_pipe.py
variants and retry_kinds). No game data, no compiler. Stdlib only.

When the original's last write before its rts is a known register, the C has to return in that register. The list of declarations to try
still held the other ones as fallbacks, and equiv.py compares only the register the C declares: a function that returns a float in fr0
and was tried as `int` passed on r0 alone (a leftover), then retcheck refused the build, and a `void` one handed its callers a leftover.

    check.py      a tiny function in a temp repo, listed by variants() and by retry_kinds() (the kinds a function that differed only in its
                  return value is tried again with):
                    fr0   `mov #5,r0; rts; fldi1 fr0` (the slot writes fr0): only fr0 is tried
                    r0    `fldi1 fr0; rts; mov #5,r0` (the slot writes r0): only r0 is tried
                    none  `rts; nop`: no value is returned, void is the one tried; the retry may try any of the three
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
W = lambda ws: b''.join(struct.pack('<H', w) for w in ws)

FUNCTIONS = {
    'fr0': [0xE005, 0x000B, 0xF09D],
    'r0': [0xF09D, 0x000B, 0xE005],
    'none': [0x000B, 0x0009],
}


class TestReturnReg(unittest.TestCase):
    def variants(self, words, call='variants'):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        code = W(words) + (W([0x0009]) if len(words) % 2 else b'')
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d f\n' % (BASE, len(code)))
        os.makedirs(os.path.join(tmp, 'src'))
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_pipe\n"
                  "print('VARIANTS', ' '.join(gen_pipe.%s('f', False) if '%s' == 'variants' else gen_pipe.%s('f')))\n" % (call, call, call))
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        for line in out.splitlines():
            if line.startswith('VARIANTS'):
                return line.split()[1:]
        return ['ERROR: ' + out[-300:]]

    def test_returnreg(self):
        got = {k: self.variants(w) for k, w in FUNCTIONS.items()}
        want = {'fr0': ['fr0'], 'r0': ['r0'], 'none': ['void']}
        if got != want:
            self.fail('[ERROR] returnreg check failed: declarations tried %r, expected %r' % (got, want))
        got = {k: self.variants(w, 'retry_kinds') for k, w in FUNCTIONS.items()}
        want = {'fr0': ['fr0'], 'r0': ['r0'], 'none': ['r0', 'fr0', 'void']}
        if got != want:
            self.fail('[ERROR] returnreg check failed: retry kinds %r, expected %r' % (got, want))


if __name__ == '__main__':
    unittest.main()
