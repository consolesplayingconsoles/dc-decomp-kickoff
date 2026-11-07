#!/usr/bin/env python3
"""A product added by an fadd is a statement of its own in the C (scripts/tools/5-generated/gen_equiv/gen_core.py). No game data, no compiler.
Stdlib only.

`fmul fr5,fr4; fadd fr4,fr6` rounds the product, then adds: two roundings. Written `f6 + (f4 * f5)` in one expression the compiler fuses it
into an fmac (one rounding) and the result differs by a bit: Zombie Revenge FUN_0c0d3f0c wrote a float one bit off.

    check.py      the function above:
                    own       the product is not an operand of the sum inside one expression
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

FN = [0xF452,                         # fmul fr5,fr4
      0xF640,                         # fadd fr4,fr6
      0xF06C,                         # fmov fr6,fr0
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
        elif re.search(r'\+ \(\w+ \* \w+\)|\(\w+ \* \w+\) \+', out):
            bad.append('own: the product is added inside one expression (the compiler fuses it into an fmac):\n%s' % out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] faddsep check failed:\n' + '\n'.join(bad))
    print('[faddsep] ok: a product added by an fadd is a statement of its own')


if __name__ == '__main__':
    main()
