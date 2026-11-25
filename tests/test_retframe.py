#!/usr/bin/env python3
"""A function that returns the stack pointer has its frame placeholder resolved (scripts/tools/5-generated/gen_equiv/gen_drv.py). No game
data, no compiler. Stdlib only.

The return line is added after the frame offsets are settled, so `return ((int)stk + @@F:0@@);` kept the placeholder and did not compile.

    check.py      `mov r15,r0; rts; nop`, written as returning r0:
                    resolved  no `@@` is left in the C
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
L = lambda v: struct.pack('<I', v)


def run_in_repo(code, script):
    """The output of a python script run in a small repo (one function `fn` made of these bytes) that has a copy of the tools."""
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d fn\n' % (BASE, len(code)))
        os.makedirs(os.path.join(tmp, 'src'))
        return subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, universal_newlines=True).stdout
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def build(code, ret):
    """The C the generator writes for the function, or the text 'SKIPPED reason'."""
    return run_in_repo(code, "import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                             "try:\n"
                             "    print(gen_drv.build('fn', %r, False)[0])\n"
                             "except gen_core.Skip as e:\n"
                             "    print('SKIPPED ' + str(e))\n" % ret)


RET_R15 = W([0x60F3, 0x000B, 0x0009])              # mov r15,r0 / rts / nop


class TestRetFrame(unittest.TestCase):
    def test_retframe(self):
        out = build(RET_R15, 'r0')
        if '@@' in out or 'stk' not in out:
            self.fail('[ERROR] retframe check failed:\nresolved: the frame address is not written out:\n%s' % out)


if __name__ == '__main__':
    unittest.main()
