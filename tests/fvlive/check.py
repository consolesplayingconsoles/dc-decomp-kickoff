#!/usr/bin/env python3
"""Register liveness counts the four floats of a vector operand (fv0 is fr0-fr3): fipr and ftrv read them
(scripts/tools/5-generated/gen_equiv/gen_core.py, reg_liveness). No game data, no compiler. Stdlib only.

The liveness saw no register in `fipr fv4,fv0`, so the floats loaded for it in another block of the flat form were taken for dead
and never written (Zombie Revenge FUN_0c9df220: fr2 and fr4-fr6, loaded before a loop, used by an ftrv and a fipr inside it).

    check.py      the liveness of `fmov.s @r4+,fr4; fipr fv4,fv0; rts; nop` on entry to the fipr:
                    vector    fr4-fr7 and fr0-fr3 are live there
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

FN = [0xF449,                       # fmov.s @r4+,fr4
      0xF4ED,                       # fipr fv4,fv0
      0x000B, 0x0009]               # rts / nop


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
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core\n"
                  "ins = [('fmov.s', '@r4+,fr4', 0), ('fipr', 'fv4,fv0', 2), ('rts', '', 4), ('nop', '', 6)]\n"
                  "print(sorted(gen_core.reg_liveness(ins, {0: 0, 2: 1, 4: 2, 6: 3})[1]))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        if not all("'fr%d'" % k in out for k in range(8)):
            bad.append('vector: fr0-fr7 are not all live at the fipr: %s' % out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] fvlive check failed:\n' + '\n'.join(bad))
    print('[fvlive] ok: a vector operand reads its four floats')


if __name__ == '__main__':
    main()
