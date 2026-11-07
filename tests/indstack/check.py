#!/usr/bin/env python3
"""A call through a pointer passes the frame's words at SP, as the integers a callee takes past a7
(scripts/tools/5-generated/gen_equiv/gen_core.py, do_call). No game data, no compiler. Stdlib only.

The target of a call through a pointer is not known when the C is written, and one that takes stack arguments reads the words at
SP: the function's own local there, then the words above it. The C cast the pointer to a one-argument function, so the callee read
the C's own outgoing area instead (Zombie Revenge FUN_0c0e15d4: a ring walker keeps the next node in a local at SP and calls the
node's handler; the checker found the handler's stack words different).

    check.py      a function that saves pr, makes a one-word local at SP, stores r4 in it through its address and calls through @(4,r4):
                    written   the generator writes it
                    words     the cast of the call takes the register arguments and the frame's words (more than one argument)
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
      0x7FFC,                       # add #-4,r15
      0x61F3, 0x2142,               # mov r15,r1 / mov.l r4,@r1 (the local, through its address)
      0x5241,                       # mov.l @(4,r4),r2
      0x420B, 0x0009,               # jsr @r2 / nop
      0x7F04,                       # add #4,r15
      0x4F26,                       # lds.l @r15+,pr
      0x000B, 0x0009]               # rts / nop


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
        elif len(m.group(1).split(',')) < 5:
            bad.append('words: the cast takes only %s, not the frame\'s words:\n%s' % (m.group(1), out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] indstack check failed:\n' + '\n'.join(bad))
    print('[indstack] ok: a call through a pointer passes the frame words at SP')


if __name__ == '__main__':
    main()
