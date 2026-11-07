#!/usr/bin/env python3
"""The frame array does not include the registers the prologue saves (scripts/tools/5-generated/gen_equiv/gen_core.py, gen_drv.py). No game
data, no compiler. Stdlib only.

`int stk[N]` is the original's frame, reached by address (`(int)stk + K` is SP + K). It was sized from the original's whole stack depth, the
registers pushed in the prologue included, and the compiler pushes its own registers again below the array: the C's locals sat that many
bytes lower than the original's, and an address of a local stored anywhere (a global, a callee's argument) differed (Zombie Revenge
kmRenderTexture: 0x...88 in the original, 0x...68 in the C; the frame was 32 bytes bigger).

    check.py      a function that saves r14 and pr, takes a 16-byte frame and calls a callee with the address of its first local:
                    size      the array holds the 16-byte frame (and the one word below SP the generator keeps), not the saved registers too
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

CALLEE = [0x000B, 0x0009]                            # a callee: rts / nop
CALLER = [0x2FE6,                                    # mov.l r14,@-r15
          0x4F22,                                    # sts.l pr,@-r15
          0x7FF0,                                    # add #-16,r15
          0x64F3,                                    # mov r15,r4        (the address of the frame's first local)
          0xBFF9, 0x0009,                            # bsr callee / nop
          0x7F10,                                    # add #16,r15
          0x4F26,                                    # lds.l @r15+,pr
          0x000B, 0x6EF6]                            # rts / mov.l @r15+,r14


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
            'int callee(int a4)\n{\n    return a4;\n}\n')
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                  "try:\n"
                  "    print(gen_drv.build('caller', 'r0', False)[0])\n"
                  "except gen_core.Skip as e:\n"
                  "    print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        m = re.search(r'int stk\[(\d+)\]', out)
        if not m:
            bad.append('size: no frame array in the generated C:\n%s' % out)
        elif int(m.group(1)) > 5:
            bad.append('size: the frame array has %s words, the frame is 16 bytes (4 words) and the saved r14 and pr are not part of it:\n%s' % (m.group(1), out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] framesaves check failed:\n' + '\n'.join(bad))
    print('[framesaves] ok: the frame array leaves out the registers the prologue saves')


if __name__ == '__main__':
    main()
