#!/usr/bin/env python3
"""An argument register the function never touched is its own incoming argument in every arm of an if, also the one that continues after
an arm that returned (scripts/tools/5-generated/gen_equiv/gen_core.py). No game data, no compiler. Stdlib only.

Zombie Revenge FUN_0c0307c0: `if (state == 0) { call(x) } else if (state == 1) { ... call(y); tail }`: the arm that made a call first left
its popped registers behind, and the continuation passed `t5, t6, t7`, variables nothing sets, where the original passed r5-r7 as they came.

    check.py      `tst r4,r4; bt L; <call other; rts>; L: call callee (reads r4-r7)`:
                    own       the call in the L arm passes a5, a6, a7 (not tN variables)
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

OTHER = [0x000B, 0x0009]                             # int other(void): rts / nop
CALLEE = [0x345C, 0x376C, 0x347C, 0x6043, 0x000B, 0x0009]    # add r5,r4 / add r6,r7 / add r7,r4 / mov r4,r0 / rts / nop
CALLER = [0x2448, 0x8905,                            # tst r4,r4 / bt L
          0x4F22, 0xBFF3, 0x0009,                    # sts.l pr / bsr other / nop
          0x4F26, 0x000B, 0x0009,                    # lds.l pr / rts / nop
          0x4F22, 0xBFEF, 0x0009,                    # L: sts.l pr / bsr callee / nop
          0x4F26, 0x000B, 0x0009]                    # lds.l pr / rts / nop


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        other, callee, caller = W(OTHER), W(CALLEE), W(CALLER)
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(other + callee + caller)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d other\nF %08x %d callee\nF %08x %d caller\n'
                                                           % (BASE, len(other), BASE + len(other), len(callee), BASE + len(other) + len(callee), len(caller)))
        os.makedirs(os.path.join(tmp, 'src'))
        open(os.path.join(tmp, 'src', 'callee.c'), 'w').write(
            'int other(void)\n{\n    return 0;\n}\nint callee(int a, int b, int c, int d)\n{\n    return a + b + c + d;\n}\n')
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                  "try:\n"
                  "    print(gen_drv.build('caller', 'r0', False)[0])\n"
                  "except gen_core.Skip as e:\n"
                  "    print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        calls = re.findall(r'\bcallee\(([^;]*)\);', out)
        if not calls:
            bad.append('own: no call to callee in the generated C:\n%s' % out)
        elif not all(re.search(r'\ba5\b', c) and re.search(r'\ba6\b', c) and re.search(r'\ba7\b', c) and not re.search(r'\bt\d+\b', c.split(',', 1)[1]) for c in calls):
            bad.append('own: a call passes variables nothing sets instead of a5, a6, a7:\n%s' % out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] armargs check failed:\n' + '\n'.join(bad))
    print('[armargs] ok: the arm after a returning arm passes its own arguments')


if __name__ == '__main__':
    main()
