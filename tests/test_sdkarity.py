#!/usr/bin/env python3
"""A library function's own source decides its arguments over the scan of its code (scripts/tools/5-generated/gen_equiv/gen_core.py
callee_arity). No game data, no compiler. Stdlib only.

The arity scan counts the registers a function reads before writing them, also those it only passes on to a callee. A library server
declared `(void)` in the SDK source was counted as taking three: every caller passed three registers it never set, the draw threw out
nearly all its cases as depending on them, and the caller was skipped, "the original does not finish on the cases" (14 of 102 library
functions with source were counted high like this).

    check.py      a temp repo with three functions that read r4 and r5 before writing them:
                    void      with sdk-source/<name>.c declaring it `(void)`: no arguments
                    mixed     with sdk-source/<name>.c declaring `(Float x, Sint32 n, void *p)`: two integer and one float argument
                    scan      with no source: the scan's two integer arguments
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
READS_R4_R5 = [0x6043, 0x305C, 0x000B, 0x0009]          # mov r4,r0; add r5,r0; rts; nop
SOURCES = {'voidfn': '/* the server */\nSint32 voidfn(void)\n{\n\treturn 0;\n}\n',
           'mixedfn': 'Sint32 mixedfn(Float x, Sint32 n, void *p)\n{\n\treturn n;\n}\n'}


class TestSdkArity(unittest.TestCase):
    def test_sdkarity(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        code = b''.join(struct.pack('<H', w) for w in READS_R4_R5 * 3)
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F 0c010000 8 voidfn\nF 0c010008 8 mixedfn\nF 0c010010 8 scanfn\n')
        os.makedirs(os.path.join(tmp, 'src'))
        os.makedirs(os.path.join(tmp, 'sdk-source'))
        for n, t in SOURCES.items():
            open(os.path.join(tmp, 'sdk-source', n + '.c'), 'w').write(t)
        script = ("import sys; sys.path.insert(0, 'tools'); sys.path.insert(0, 'tools/5-generated/gen_equiv'); import toolpath, gen_core\n"
                  "for n in ('voidfn', 'mixedfn', 'scanfn'): print('ARITY', n, gen_core.callee_arity(n))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True).stdout
        got = {l.split()[1]: l.split(None, 2)[2] for l in out.splitlines() if l.startswith('ARITY')}
        want = {'voidfn': '(0, 0)', 'mixedfn': '(2, 1)', 'scanfn': '(2, 0)'}
        if got != want:
            self.fail('[ERROR] sdkarity check failed: %r, expected %r\n%s' % (got, want, out[-600:]))


if __name__ == '__main__':
    unittest.main()
