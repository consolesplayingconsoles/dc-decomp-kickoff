#!/usr/bin/env python3
"""The one-bit shifts set T to the bit they shift out (scripts/tools/5-generated/gen_equiv/gen_core.py). No game data, no compiler.
Stdlib only.

shlr and shar leave bit 0 in T, shll and shal bit 31. The generator did not set T for them, so a bt, bf, rotcl, addc or movt after one
read a flag from before it (or stopped on "no T"). Zombie Revenge FUN_0c0c4ff0, an LZ decompressor that tests each bit it shifts out of the
flag byte, tested `t3 == 0` (the dt before) where the original tested the shifted-out bit: the C never ended.

    check.py      `shlr r4; bt L; mov #1,r0; rts; nop; L: mov #2,r0; rts; nop` and the same with shll (bf):
                    shlr      the C branches on bit 0 of the value shifted
                    shll      the C branches on bit 31 of the value shifted
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

SHLR = [0x4401, 0x8902, 0xE001, 0x000B, 0x0009, 0xE002, 0x000B, 0x0009]      # shlr r4 / bt L / mov #1,r0 / rts / nop / L: mov #2,r0 / rts / nop
SHLL = [0x4400, 0x8B02, 0xE001, 0x000B, 0x0009, 0xE002, 0x000B, 0x0009]      # shll r4 / bf L / ...


def build(tmp, fn):
    code = W(fn)
    open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
    open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
    open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d xform\n' % (BASE, len(code)))
    os.makedirs(os.path.join(tmp, 'src'), exist_ok=True)
    script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
              "try:\n"
              "    print(gen_drv.build('xform', 'r0', False)[0])\n"
              "except gen_core.Skip as e:\n"
              "    print('SKIPPED ' + str(e))\n")
    return subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        out = build(tmp, SHLR)
        if 'SKIPPED' in out or 'xform' not in out:
            bad.append('shlr: the generator did not write it:\n%s' % out)
        elif not re.search(r'a4\)? ?& ?(0x)?1\b', out):
            bad.append('shlr: the C does not branch on bit 0 of a4:\n%s' % out)
        out = build(tmp, SHLL)
        if 'SKIPPED' in out or 'xform' not in out:
            bad.append('shll: the generator did not write it:\n%s' % out)
        elif not re.search(r'a4\)? ?>> ?31|a4\)? ?& ?(0x)?80000000', out):
            bad.append('shll: the C does not branch on bit 31 of a4:\n%s' % out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] shiftt check failed:\n' + '\n'.join(bad))
    print('[shiftt] ok: shlr and shll leave the bit they shift out in T')


if __name__ == '__main__':
    main()
