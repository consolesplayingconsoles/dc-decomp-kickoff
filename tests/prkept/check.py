#!/usr/bin/env python3
"""A return address kept in a register is written: `sts pr,r12` before a call and `lds r12,pr` after it
(scripts/tools/5-generated/gen_equiv/gen_core.py). No game data, no compiler. Stdlib only.

The generator stopped on `sts pr,r12` (Zombie Revenge FUN_0c9df220): the return address is not a value the C has, but a function
that puts it in a register and takes it back after its calls has not changed it.

    check.py      a callee returning 5 and a caller `push r12; sts pr,r12; bsr callee; nop; lds r12,pr; pop r12; rts; nop`:
                    written   the generator writes the caller
                    call      the C calls callee
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

CALLEE = [0xE005, 0x000B, 0x0009, 0x0009]            # mov #5,r0 / rts / nop / (pad)
CALLER = [0x2FC6,                                    # mov.l r12,@-r15
          0x0C2A,                                    # sts pr,r12
          0xB000 | 0xFF8, 0x0009,                    # bsr callee / nop  (offset patched below)
          0x4C2A,                                    # lds r12,pr
          0x6CF6, 0x000B, 0x0009]                    # mov.l @r15+,r12 / rts / nop


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
        sys.exit('[ERROR] prkept check failed:\n' + '\n'.join(bad))
    print('[prkept] ok: a return address kept in a register is written')


if __name__ == '__main__':
    main()
