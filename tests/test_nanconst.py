#!/usr/bin/env python3
"""A NaN or infinity float constant is written as a name the file declares (scripts/tools/5-generated/gen_equiv/gen_core.py ffmt and
gen_drv.py head_protos). No game data, no compiler. Stdlib only.

`(*(float*)&(unsigned int){0xFFFFFFFF})` takes the address of a compound literal, which the compiler rejects: a function that loaded such a
constant never compiled. The bits are now a `static const unsigned int fbits_<bits>` at the top of the file.

    check.py      ffmt(0xFFFFFFFF):
                    named     no compound literal, the name `fbits_FFFFFFFF`
                    declared  head_protos declares that constant, once
                  ffmt(0x3F800000):
                    plain     an ordinary float is written as before (`1.0f`)
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


SCRIPT = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
          "t = gen_core.ffmt(0xFFFFFFFF)\n"
          "print(t)\n"
          "print(gen_drv.head_protos([('fn', 'int fn(void)\\n{\\n    float u0;\\n    u0 = %s;\\n    return 0;\\n}' % t, None, {})]))\n"
          "print('PLAIN ' + gen_core.ffmt(0x3F800000))\n")


class TestNanConst(unittest.TestCase):
    def test_nanconst(self):
        out = run_in_repo(W([0x000B, 0x0009]), SCRIPT)
        lines = out.splitlines()
        bad = []
        if not lines or 'unsigned int){' in lines[0] or 'fbits_FFFFFFFF' not in lines[0]:
            bad.append('named: the constant is not a declared name:\n%s' % out)
        if out.count('static const unsigned int fbits_FFFFFFFF = 0xFFFFFFFF;') != 1:
            bad.append('declared: the file does not declare the constant once:\n%s' % out)
        if 'PLAIN 1.0f' not in out:
            bad.append('plain: an ordinary float changed:\n%s' % out)
        if bad:
            self.fail('[ERROR] nanconst check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
