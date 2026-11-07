#!/usr/bin/env python3
"""A float converted from an integer sum is converted as a signed integer (scripts/tools/5-generated/gen_equiv/gen_core.py). No game data, no
compiler. Stdlib only.

`float fpul` converts a signed 32-bit integer. The generator wrote `(float)(a4 + 0xFFFF8000)`, and in C a hex constant above 0x7FFFFFFF is
unsigned, so the sum was converted as an unsigned value (about 4.29e9 where the original had a small negative number): Zombie Revenge
FUN_0c054654 wrote another angle on the cases where the difference was negative.

    check.py      `mov #-128,r2; add r4,r2; lds r2,fpul; float fpul,fr0; rts; nop`:
                    signed    the sum is cast to int before it is converted to float
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
BASE = 0x0C010000
W = lambda ws: b''.join(struct.pack('<H', w) for w in ws)

FN = [0xE280,                         # mov #-128,r2
      0x324C,                         # add r4,r2
      0x425A,                         # lds r2,fpul
      0xF02D,                         # float fpul,fr0
      0x000B, 0x0009]                 # rts / nop


def build(tmp, fn):
    code = W(fn)
    open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
    open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
    open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d xform\n' % (BASE, len(code)))
    os.makedirs(os.path.join(tmp, 'src'), exist_ok=True)
    script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
              "try:\n"
              "    print(gen_drv.build('xform', 'fr0', False)[0])\n"
              "except gen_core.Skip as e:\n"
              "    print('SKIPPED ' + str(e))\n")
    return subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        out = build(tmp, FN)
        if 'SKIPPED' in out or 'xform' not in out:
            bad.append('written: the generator did not write it:\n%s' % out)
        elif not re.search(r'\(float\)\(int\)', out):
            bad.append('signed: the sum is converted to float without an int cast:\n%s' % out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] floatsigned check failed:\n' + '\n'.join(bad))
    print('[floatsigned] ok: a float converted from an integer sum is converted as signed')


if __name__ == '__main__':
    main()
