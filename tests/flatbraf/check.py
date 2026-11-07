#!/usr/bin/env python3
"""The flat form writes `and #K,r0; braf r0` over a table of two-word `bra` stubs: the masked value can only be one of the multiples
of 4 under the mask, each one a stub (scripts/tools/5-generated/gen_equiv/gen_core.py). No game data, no compiler. Stdlib only.

The flat form stopped on every braf it could not read a constant or a mova/mov.w offset table for ("flat: braf", Zombie Revenge
FUN_0c9e2048: `and #42,r0 ... and #28,r0 ; braf r0` over eight stubs).

    check.py      `mov r4,r0; and #4,r0; braf r0; nop; bra A; nop; bra B; nop; A: mov #1,r0; rts; nop; B: mov #2,r0; rts; nop`, flat:
                    written   the generator writes it
                    switch    the C switches on the masked value and has both cases
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

FN = [0x6043, 0xC904, 0x0023, 0x0009,         # mov r4,r0 / and #4,r0 / braf r0 / nop
      0xA002, 0x0009, 0xA003, 0x0009,         # bra A / nop / bra B / nop
      0xE001, 0x000B, 0x0009,                 # A: mov #1,r0 / rts / nop
      0xE002, 0x000B, 0x0009]                 # B: mov #2,r0 / rts / nop


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
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, env=dict(os.environ, GEN_FORM='flat'), stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        if 'SKIPPED' in out or 'xform' not in out:
            bad.append('written: the generator did not write it:\n%s' % out)
        elif 'switch' not in out or 'case 0' not in out or 'case 4' not in out:
            bad.append('switch: no switch with case 0 and case 4 in the C:\n%s' % out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] flatbraf check failed:\n' + '\n'.join(bad))
    print('[flatbraf] ok: a braf over a table of bra stubs is written as a switch')


if __name__ == '__main__':
    main()
