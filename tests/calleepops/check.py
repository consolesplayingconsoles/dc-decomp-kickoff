#!/usr/bin/env python3
"""A callee that pops the words its caller pushed (`rts` with `add #N,r15` in the delay slot) leaves the caller's stack that much lower
(scripts/tools/5-generated/gen_equiv/gen_core.py). No game data, no compiler. Stdlib only.

The generator took the pushed words to stay on the stack after the call, so a caller with one path that pushes and calls such a
routine and another that does not reached its epilogue at two depths ("flat: stack depth differs", Zombie Revenge FUN_0c0f271e,
whose callee FUN_0c0f3bf4 ends `rts` / `add #16,r15`).

    check.py      a callee `mov.l @r15,r0; bra L; nop; L: rts; add #4,r15` (it returns through a branch) and a caller that pushes a word and calls it on one path only:
                    written   the generator writes the caller
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

CALLEE = [0x60F2, 0xA000, 0x0009, 0x000B, 0x7F04, 0x0009]    # mov.l @r15,r0 / bra L / nop / L: rts / add #4,r15 / (pad)
CALLER = [0x4F22,                                    # sts.l pr,@-r15
          0x2448, 0x8903,                            # tst r4,r4 / bt L (over the push and the call)
          0xE501, 0x2F56,                            # mov #1,r5 / mov.l r5,@-r15
          0xBFF3, 0x0009,                            # bsr callee / nop
          0x4F26, 0x000B, 0x0009]                    # L: lds.l @r15+,pr / rts / nop


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
            'int callee(void)\n{\n    return 5;\n}\n')
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                  "try:\n"
                  "    print(gen_drv.build('caller', 'r0', False)[0])\n"
                  "except gen_core.Skip as e:\n"
                  "    print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        if 'SKIPPED' in out or 'caller' not in out:
            bad.append('written: the generator did not write it:\n%s' % out)
        elif not re.search(r'\bcallee\(', out):
            bad.append('call: no call to callee in the generated C:\n%s' % out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] calleepops check failed:\n' + '\n'.join(bad))
    print('[calleepops] ok: a callee that pops its arguments leaves the stack lower')


if __name__ == '__main__':
    main()
