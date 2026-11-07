#!/usr/bin/env python3
"""Pair moves into the matrix bank are one load of the matrix, not a round trip each
(scripts/tools/5-generated/gen_equiv/gen_drv.py merge_ext). No game data, no compiler. Stdlib only.

Each pair move into the back bank (an XD register) was written as `_builtin_st_ext(m); m[i] = ...; m[i+1] = ...; _builtin_ld_ext(m);`.
A matrix loaded from memory took eight of them (Zombie Revenge nlLoadMatrix8: 40 bytes, 820 in C).

    check.py      a function that does fschg, two pair loads into xd0 and xd2 (fmov @r4+,fr1 / fr3 in size mode 1), fschg:
                    one       the C loads the matrix once (one _builtin_ld_ext) and stores it at most once
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
      0xF149, 0xF349,               # fmov @r4+,xd0 / fmov @r4+,xd2
      0xF3FD,                       # fschg
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
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                  "try:\n"
                  "    print(gen_drv.build('xform', 'void', False)[0])\n"
                  "except gen_core.Skip as e:\n"
                  "    print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        if 'SKIPPED' in out or 'xform' not in out:
            bad.append('written: the generator did not write it:\n%s' % out)
        elif out.count('_builtin_ld_ext(') != 1 or out.count('_builtin_st_ext(') > 1:
            bad.append('one: the matrix is loaded %d times, stored %d times:\n%s' % (out.count('_builtin_ld_ext('), out.count('_builtin_st_ext('), out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] extmerge check failed:\n' + '\n'.join(bad))
    print('[extmerge] ok: pair moves into the matrix bank are one load of the matrix')


if __name__ == '__main__':
    main()
