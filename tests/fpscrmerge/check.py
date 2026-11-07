#!/usr/bin/env python3
"""An `lds rN,fpscr` of a value merged from memory and the current FPSCR is written, the way a value carried in a variable is
(scripts/tools/5-generated/gen_equiv/gen_core.py). No game data, no compiler. Stdlib only.

The generator stopped on "lds fpscr not a restore" when the value was not a plain mask of the FPSCR it read (Zombie Revenge
FUN_0c0e35b6, a context restore: the new FPSCR is the memory word with the current FR bit kept,
`(mem & ~FR) | (fpscr & FR)`). It writes the value as it is; the check catches a mode the generator did not follow.

    check.py      `sts fpscr,r3; mov #32,r1; shll16 r1; mov.l @r5,r0; not r1,r2; and r1,r3; and r2,r0; or r3,r0; lds r0,fpscr; rts`:
                    written   the generator writes it
                    set       the C calls _builtin_set_fpscr
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
BASE = 0x0C010000
W = lambda ws: b''.join(struct.pack('<H', w) for w in ws)

FN = [0x036A,                         # sts fpscr,r3
      0xE120, 0x4128,                 # mov #32,r1 / shll16 r1 (the FR bit)
      0x6052,                         # mov.l @r5,r0
      0x6217, 0x2319, 0x2029, 0x203B, # not r1,r2 / and r1,r3 / and r2,r0 / or r3,r0
      0x406A,                         # lds r0,fpscr
      0x000B, 0xE000]                 # rts / mov #0,r0


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        code = W(FN)
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d xform\n' % (BASE, len(code)))
        os.makedirs(os.path.join(tmp, 'src'))
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                  "try:\n"
                  "    print(gen_drv.build('xform', 'r0', False)[0])\n"
                  "except gen_core.Skip as e:\n"
                  "    print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        if 'SKIPPED' in out or 'xform' not in out:
            bad.append('written: the generator did not write it:\n%s' % out)
        elif '_builtin_set_fpscr(' not in out:
            bad.append('set: no _builtin_set_fpscr in the C:\n%s' % out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] fpscrmerge check failed:\n' + '\n'.join(bad))
    print('[fpscrmerge] ok: an FPSCR value merged from memory is written')


if __name__ == '__main__':
    main()
