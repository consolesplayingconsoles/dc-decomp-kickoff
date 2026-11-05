#!/usr/bin/env python3
"""A call passes every stack word its callee's definition takes, not only the ones the callee's code reads
(scripts/tools/5-generated/gen_equiv/gen_core.py, own_stack). No game data, no compiler. Stdlib only.

The words a call pushed were cut to the number the callee's code reads directly, on the idea that the words below them were an earlier
call's, whose stack adjustment was put off. A callee whose definition takes seven integers but reads only the first stack word (the
others are unused) lost the two it did not read: the C passed five arguments where the original passed seven, and the stack words
the callee's own callees see differed (Zombie Revenge kmSetSystemConfiguration -> kmiGetVertexBasePointer).

    check.py      a callee `int callee(int a4, ..., int a10)` that reads only the word at SP, and a caller that pushes three words and
                  calls it, the stack dropped by the add after the call:
                    seven     the call in the generated C has seven arguments (it had five)
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

CALLEE = [0x60F2, 0x000B, 0x0009, 0x0009]            # mov.l @r15,r0 / rts / nop / (pad)
CALLER = [0x4F22,                                    # sts.l pr,@-r15
          0xE500, 0xE600, 0xE700,                    # mov #0,r5 / r6 / r7
          0x2F46, 0x2F56, 0x2F66,                    # mov.l r4,@-r15 / mov.l r5,@-r15 / mov.l r6,@-r15
          0xBFF3, 0x6443,                            # bsr callee / mov r4,r4 (delay slot)
          0x7F0C, 0x4F26, 0x000B, 0x0009]            # add #12,r15 / lds.l @r15+,pr / rts / nop


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
            'int callee(int a4, int a5, int a6, int a7, int a8, int a9, int a10)\n{\n    return a8;\n}\n')
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                  "try:\n"
                  "    print(gen_drv.build('caller', 'r0', False)[0])\n"
                  "except gen_core.Skip as e:\n"
                  "    print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        m = re.search(r'\bcallee\(([^;]*)\);', out)
        if not m:
            bad.append('seven: no call to callee in the generated C:\n%s' % out)
        else:
            n = len([x for x in m.group(1).split(',') if x.strip()])
            if n != 7:
                bad.append('seven: the call passes %d arguments, the callee takes 7 and three words were pushed:\n%s' % (n, out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] pushedwords check failed:\n' + '\n'.join(bad))
    print('[pushedwords] ok: a call passes the stack words its callee\'s definition takes')


if __name__ == '__main__':
    main()
