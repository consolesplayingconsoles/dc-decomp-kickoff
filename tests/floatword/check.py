#!/usr/bin/env python3
"""A float pushed in a place the callee's definition takes an integer goes as its bits
(scripts/tools/5-generated/gen_equiv/gen_core.py, do_call). No game data, no compiler. Stdlib only.

A call passed the pushed floats as floats, and the callee, defined with integers past a7, got them converted to integers (Zombie
Revenge FUN_0c056588 -> FUN_0c0a7064: seven integer words past a7, five of them floats pushed with fmov.s).

    check.py      a callee `int callee(int a4, ..., int a9)` and a caller that loads 1.0f and pushes it twice, then calls:
                    bits      the two stack arguments are read from the frame as integers, not passed as floats
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

CALLEE = [0x000B, 0x0009]            # rts / nop
CALLER = [0x4F22,                    # sts.l pr,@-r15
          0xF19D,                    # fldi1 fr1
          0xFF1B, 0xFF1B,            # fmov.s fr1,@-r15 (twice)
          0xE400, 0xE500, 0xE600, 0xE700,
          0xBFF4, 0x0009,            # bsr callee / nop
          0x7F08, 0x4F26, 0x000B, 0x0009]


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        callee, caller = W(CALLEE), W(CALLER)
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(callee + caller)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d callee\nF %08x %d caller\n'
                                                           % (BASE, len(callee), BASE + len(callee), len(caller)))
        os.makedirs(os.path.join(tmp, 'src'))
        open(os.path.join(tmp, 'src', 'callee.c'), 'w').write(
            'int callee(int a4, int a5, int a6, int a7, int a8, int a9)\n{\n    return a8 + a9;\n}\n')
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                  "try:\n"
                  "    print(gen_drv.build('caller', 'r0', False)[0])\n"
                  "except gen_core.Skip as e:\n"
                  "    print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        call = [l for l in out.split('\n') if 'callee(' in l]
        if 'SKIPPED' in out or not call:
            bad.append('written: the generator did not write it:\n%s' % out)
        elif '*(int *)((int)stk' not in call[0]:
            bad.append('bits: the floats are passed as values, not as the words in the frame:\n%s' % out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] floatword check failed:\n' + '\n'.join(bad))
    print('[floatword] ok: a float in an integer place goes as its bits')


if __name__ == '__main__':
    main()
