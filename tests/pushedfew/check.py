#!/usr/bin/env python3
"""A word pushed for a call is an argument when the callee reads stack words, though the caller pushes fewer than it reads
(scripts/tools/5-generated/gen_equiv/gen_core.py, do_call). No game data, no compiler. Stdlib only.

The generator took the words pushed for a call whose callee reads four register arguments as "saved, not passed" (a callee taking at most four
integers has no stack arguments), so the C did not pass them and the callee read its caller's frame instead (Zombie Revenge
kmiSetTAEnvironment -> kmiCreateRegionArray, which reads four registers and eight stack words: the original pushed two). The words the
callee reads past the pushed ones are leftovers; the pushed ones are its first stack arguments.

    check.py      a callee (no C definition) reading r4-r7 and two stack words, and a caller that pushes one word and calls it:
                    pushed    the call in the generated C passes the pushed value (a fifth argument), not nothing
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

CALLEE = [0x345C, 0x376C, 0x347C,                     # add r5,r4 / add r6,r7 / add r7,r4   (reads r4-r7)
          0x60F2, 0x51F1, 0x301C, 0x340C,            # mov.l @r15,r0 / mov.l @(4,r15),r1 / add r1,r0 / add r0,r4
          0x6043, 0x000B, 0x0009, 0x0009]            # mov r4,r0 / rts / nop / (pad)
CALLER = [0x4F22,                                    # sts.l pr,@-r15
          0x2F56,                                    # mov.l r5,@-r15   (the pushed word)
          0xBFF1, 0x0009,                            # bsr callee / nop
          0x7F04,                                    # add #4,r15
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
        # no C definition of the callee: its arity and its stack words come from its original code (as for kmiCreateRegionArray)
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                  "try:\n"
                  "    print(gen_drv.build('caller', 'r0', False)[0])\n"
                  "except gen_core.Skip as e:\n"
                  "    print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        m = re.search(r'\bcallee\(([^;]*)\);', out)
        if not m:
            bad.append('pushed: no call to callee in the generated C:\n%s' % out)
        else:
            n = len([x for x in m.group(1).split(',') if x.strip()])
            if n < 5:
                bad.append('pushed: the call passes %d arguments, one word was pushed for it (a fifth argument):\n%s' % (n, out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] pushedfew check failed:\n' + '\n'.join(bad))
    print('[pushedfew] ok: a pushed word is an argument when the callee reads stack words')


if __name__ == '__main__':
    main()
