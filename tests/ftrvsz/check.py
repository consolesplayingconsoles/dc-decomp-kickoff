#!/usr/bin/env python3
"""ftrv in size mode 1 is written: the matrix product does not depend on FPSCR.SZ, only the moves around it do
(scripts/tools/5-generated/gen_equiv/gen_core.py). No game data, no compiler. Stdlib only.

The generator stopped on every ftrv while SZ was set ("ftrv in size mode 1"), which held the vertex-transform loops that switch to
pair moves with fschg for the whole function (Zombie Revenge FUN_0c0e9500 and five like it). The simulator already runs ftrv the same
in both sizes, and the pair moves around it were written.

    check.py      a function that does fschg, loads fv4 with two pair moves (fmov @r4+,dr4 / dr6), ftrv xmtrx,fv4, stores the vector
                  with two pair moves and fschg back:
                    written   the generator writes it (it skipped: ftrv in size mode 1)
                    ftrv      the C calls _builtin_ftrv on the four loaded floats
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

FN = [0xF3FD,                       # fschg
      0xF449, 0xF649,               # fmov @r4+,dr4 / fmov @r4+,dr6
      0xF5FD,                       # ftrv xmtrx,fv4
      0xF54A, 0x7508, 0xF56A,       # fmov dr4,@r5 / add #8,r5 / fmov dr6,@r5
      0xF3FD,                       # fschg
      0xE000, 0x000B, 0x0009]       # mov #0,r0 / rts / nop


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        code = W(FN) + (W([0x0009]) if len(FN) % 2 else b'')
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d xform\n' % (BASE, len(code)))
        os.makedirs(os.path.join(tmp, 'src'))
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                  "try:\n"
                  "    print(gen_drv.build('xform', 'r0', False)[0])\n"
                  "except gen_core.Skip as e:\n"
                  "    print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        if 'SKIPPED' in out or 'xform' not in out:
            bad.append('written: the generator did not write it:\n%s' % out)
        elif '_builtin_ftrv(' not in out:
            bad.append('ftrv: no _builtin_ftrv in the C:\n%s' % out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] ftrvsz check failed:\n' + '\n'.join(bad))
    print('[ftrvsz] ok: ftrv in size mode 1 is written')


if __name__ == '__main__':
    main()
