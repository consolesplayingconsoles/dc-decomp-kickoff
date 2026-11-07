#!/usr/bin/env python3
"""The flat form writes a function that switches the FPU size mode inside a block, or carries it across blocks when every path into a block has the same one
(scripts/tools/5-generated/gen_equiv/gen_core.py). No game data, no compiler. Stdlib only.

The flat form stopped on any function with an fschg or frchg in it ("flat: FPU mode changes", Zombie Revenge FUN_0c9e2048), though
what crosses between its blocks is only the registers; a mode still switched at the end of a block is still refused
("flat: FPU mode across a block").

    check.py      a function `tst r4,r4; bt L; fschg; fmov @r5,dr0; fschg; L: rts` forced into the flat form (GEN_FORM=flat):
                    written   the generator writes it
                    join      a second function whose paths meet in different modes is still refused
                    across    a third whose paths meet in the same switched mode is written
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

FN = [0x2448, 0x8902,               # tst r4,r4 / bt L
      0xF3FD,                       # fschg
      0xF058,                       # fmov @r5,dr0
      0xF3FD,                       # fschg
      0x000B, 0xE000]               # L: rts / mov #0,r0


# the mode still switched when a block ends: the generator must refuse it, not write registers it names by the wrong bank/size
FN2 = [0x2448, 0xF3FD, 0x8901, 0x0009,        # tst r4,r4 / fschg / bt L / nop
       0xF3FD, 0x000B, 0xE000]                # fschg / L: rts / mov #0,r0

# the mode switched across a block boundary, the same on every path into the block: carried with the block
FN3 = [0xF3FD, 0x2448, 0x8901, 0x0009,        # fschg / tst r4,r4 / bt L / nop
       0xF058, 0xF3FD, 0x000B, 0xE000]        # fmov @r5,dr0 / L: fschg / rts / mov #0,r0


def build(fn, tmp):
    code = W(fn) + (W([0x0009]) if len(fn) % 2 else b'')
    open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
    open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
    open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d xform\n' % (BASE, len(code)))
    os.makedirs(os.path.join(tmp, 'src'), exist_ok=True)
    script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
              "try:\n"
              "    print(gen_drv.build('xform', 'r0', False)[0])\n"
              "except gen_core.Skip as e:\n"
              "    print('SKIPPED ' + str(e))\n")
    return subprocess.run([sys.executable, '-c', script], cwd=tmp, env=dict(os.environ, GEN_FORM='flat'), stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, universal_newlines=True).stdout


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        out = build(FN, tmp)
        if 'SKIPPED' in out or 'xform' not in out:
            bad.append('written: the generator did not write it:\n%s' % out)
        out = build(FN2, tmp)
        if 'SKIPPED' not in out:
            bad.append('join: paths that meet in different modes were written:\n%s' % out)
        out = build(FN3, tmp)
        if 'SKIPPED' in out or 'xform' not in out:
            bad.append('across: a mode carried over a block boundary, the same on both paths, was not written:\n%s' % out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] flatmode check failed:\n' + '\n'.join(bad))
    print('[flatmode] ok: the flat form writes a function that switches the FPU mode inside a block, carries it across blocks, and refuses paths that meet in different modes')


if __name__ == '__main__':
    main()
