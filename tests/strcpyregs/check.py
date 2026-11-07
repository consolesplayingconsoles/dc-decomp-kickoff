#!/usr/bin/env python3
"""After the compiler's string copy helper _slow_strcpy the registers it keeps are still known (scripts/tools/5-generated/gen_equiv/
gen_core.py). No game data, no compiler. Stdlib only.

_slow_strcpy (destination r0, source r1) pushes and pops r3 and r4 (and its aligned path quick_strcpy1 r5 and r6) and leaves r0 = the
destination; only r1 is advanced. The generator dropped r0-r7 after the call, so a pointer kept in r4 across it came back as a
variable nothing sets (Zombie Revenge FUN_0c0c0f84 stored through `t2`, the original through r4).

    check.py      a caller that sets r4 = a5 + 4, copies a7 to a6 with the helper, then stores a6 through r4:
                    kept      the store goes through a5 + 4 in the generated C
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

CALLEE = [0x000B, 0x0009]                            # the helper: rts / nop (the generator knows it by its name)
CALLER = [0x4F22,                                    # sts.l pr,@-r15
          0x6453, 0x7404,                            # mov r5,r4 / add #4,r4
          0x6063, 0x6173,                            # mov r6,r0 / mov r7,r1
          0xBFF7, 0x0009,                            # bsr _slow_strcpy / nop
          0x2462,                                    # mov.l r6,@r4
          0x4F26, 0x000B, 0x0009]                    # lds.l @r15+,pr / rts / nop


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        callee, caller = W(CALLEE), W(CALLER)
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(callee + caller)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d _slow_strcpy\nF %08x %d caller\n'
                                                           % (BASE, len(callee), BASE + len(callee), len(caller)))
        os.makedirs(os.path.join(tmp, 'src'))
        open(os.path.join(tmp, 'src', 'callee.c'), 'w').write(
            'void _slow_strcpy(void)\n{\n}\n')
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                  "try:\n"
                  "    print(gen_drv.build('caller', 'r0', False)[0])\n"
                  "except gen_core.Skip as e:\n"
                  "    print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        if 'SKIPPED' in out or 'caller' not in out:
            bad.append('written: the generator did not write it:\n%s' % out)
        elif not re.search(r'a5 \+ 0x4|a5 \+ 4', out):
            bad.append('kept: the store does not go through a5 + 4 (r4 was lost across the helper):\n%s' % out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] strcpyregs check failed:\n' + '\n'.join(bad))
    print('[strcpyregs] ok: registers the string copy helper keeps are known after it')


if __name__ == '__main__':
    main()
