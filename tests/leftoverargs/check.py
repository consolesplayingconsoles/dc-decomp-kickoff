#!/usr/bin/env python3
"""A call after an earlier call, with an argument register in the middle never set since, passes it as a leftover (0)
(scripts/tools/5-generated/gen_equiv/gen_core.py). No game data, no compiler. Stdlib only.

The generator stopped on "arg gap" when the callee reads r4-r7, the function set r4 and r6 since its last call and r5, r7 hold what
that call left (Zombie Revenge FUN_0c09ec84, the tail call to FUN_0c0cc3f8). A register an earlier call has changed is a leftover
and goes as 0 (the check compares only registers the function set); the pushed-word case already did this.

    check.py      a callee `int callee(int a, int b, int c, int d)` and a caller that calls it, then sets r4 and r6 and calls it again:
                    written   the generator writes the caller
                    zero      the second call passes r4=1, r5=0 (the leftover), r6=2
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

CALLEE = [0x345C, 0x376C, 0x347C, 0x6043, 0x000B, 0x0009]    # add r5,r4 / add r6,r7 / add r7,r4 / mov r4,r0 / rts / nop
CALLER = [0x4F22,                                    # sts.l pr,@-r15
          0xBFF7, 0x0009,                            # bsr callee / nop
          0xE401, 0xE602,                            # mov #1,r4 / mov #2,r6
          0xBFF3, 0x0009,                            # bsr callee / nop
          0x4F26, 0x000B, 0x0009]                    # lds.l @r15+,pr / rts / nop


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
            'int callee(int a, int b, int c, int d)\n{\n    return a + b + c + d;\n}\n')
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                  "try:\n"
                  "    print(gen_drv.build('caller', 'r0', False)[0])\n"
                  "except gen_core.Skip as e:\n"
                  "    print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        if 'SKIPPED' in out or 'caller' not in out:
            bad.append('written: the generator did not write it:\n%s' % out)
        elif '0x1, 0x0, 0x2' not in out:
            bad.append('zero: r4=1, r5 (never set since the call) as 0, r6=2 not in the second call:\n%s' % out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] leftoverargs check failed:\n' + '\n'.join(bad))
    print('[leftoverargs] ok: a leftover argument register goes as 0')


if __name__ == '__main__':
    main()
