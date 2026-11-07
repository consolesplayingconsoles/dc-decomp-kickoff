#!/usr/bin/env python3
"""A call through a pointer passes the argument registers the function never set as they came in
(scripts/tools/5-generated/gen_equiv/gen_core.py, do_call). No game data, no compiler. Stdlib only.

The target of a call through a pointer may take every argument register, and the check compares every one the original holds for it.
The C passed r4 alone, and the compiler's r5-r7 differed from the incoming ones the original passed on (Zombie Revenge FUN_0c021eba:
a handler called through the object, r5-r7 untouched).

    check.py      a function that calls through @(4,r4) with r4 alone set:
                    written   the generator writes it
                    words     the cast takes a4-a7, the incoming registers passed on
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

FN = [0x4F22,                       # sts.l pr,@-r15
      0x5241,                       # mov.l @(4,r4),r2
      0x420B, 0x0009,               # jsr @r2 / nop
      0x4F26,                       # lds.l @r15+,pr
      0x000B, 0x0009, 0x0009]       # rts / nop / (pad)


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        code = W(FN)
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d walker\n' % (BASE, len(code)))
        os.makedirs(os.path.join(tmp, 'src'))
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                  "try:\n"
                  "    print(gen_drv.build('walker', 'r0', False)[0])\n"
                  "except gen_core.Skip as e:\n"
                  "    print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        m = re.search(r'\(int \(\*\)\(([^)]*)\)\)', out)
        if 'SKIPPED' in out or not m:
            bad.append('written: the generator did not write it:\n%s' % out)
        elif len(m.group(1).split(',')) != 4 or 'a7' not in out:
            bad.append('words: the cast takes %s, not a4-a7 as they came in:\n%s' % (m.group(1), out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] indargs check failed:\n' + '\n'.join(bad))
    print('[indargs] ok: a call through a pointer passes the untouched argument registers on')


if __name__ == '__main__':
    main()
