#!/usr/bin/env python3
"""FPUL set in one block and read in the next, in the flat form (scripts/tools/5-generated/gen_equiv/gen_core.py exec_flat). No game
data, no compiler. Stdlib only.

The compiler shares a tail between paths: Virtua Tennis FUN_8c07b7aa sets FPUL (lds r3,fpul) on two paths and both reach one
`float fpul,fr3` (8c07bada bra 8c07bb1a). The flat form started every block with FPUL unknown, so the float read nothing ("undefined
@8c07bb1a") and the function had only the structured form, 2x its size.

    check.py      a function that sets FPUL on two paths and converts it after the join, written flat: it is written (not skipped),
                  and FPUL is a variable carried across the join (FPUL_)
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
BASE = 0x0C010000
W = lambda ws: b''.join(struct.pack('<H', w) for w in ws)

CODE = [0x2448,          # 00 tst r4,r4
        0x8903,          # 02 bt 0C
        0xE301,          # 04 mov #1,r3
        0x435A,          # 06 lds r3,fpul
        0xA002,          # 08 bra 10
        0x0009,          # 0A nop
        0xE302,          # 0C mov #2,r3
        0x435A,          # 0E lds r3,fpul
        0xF02D,          # 10 float fpul,fr0: the shared tail, its own block
        0x000B,          # 12 rts
        0x0009]          # 14 nop


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        code = W(CODE + [0x0009])
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d tailfn\n' % (BASE, len(code)))
        os.makedirs(os.path.join(tmp, 'src'))
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                  "try:\n"
                  "    print(gen_drv.build('tailfn', 'fr0', False)[0])\n"
                  "except gen_core.Skip as e:\n"
                  "    print('SKIPPED ' + str(e))\n")
        env = dict(os.environ, GEN_FORM='flat')
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        if 'SKIPPED' in out or '{' not in out:
            bad.append('not written flat:\n%s' % out[-600:])
        elif 'FPUL_' not in out:
            bad.append('written, but FPUL is not carried across the join:\n%s' % out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] flatfpul check failed:\n' + '\n'.join(bad))
    print('[flatfpul] ok: FPUL set before a join and read after it is a variable of the flat form')


if __name__ == '__main__':
    main()
