#!/usr/bin/env python3
"""A float pushed on the stack and popped into an integer register is the float's bits
(scripts/tools/5-generated/gen_equiv/gen_core.py). No game data, no compiler. Stdlib only.

The generator stopped on "float popped into integer register" (Zombie Revenge FUN_0c9e2048: `fmov.s fr0,@-r15 ... mov.l @r15+,r0`,
the compiler used the stack to move a float to an integer register). The word goes through the frame: stored as a float, read
back as an int.

    check.py      `fmov.s fr4,@-r15; mov.l @r15+,r0; rts; nop`:
                    written   the generator writes it
                    bits      the C stores the float and reads the word back as an int (`*(int *)`)
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

FN = [0xE100,                         # mov #0,r1 (the body: an fmov.s @-r15 first would be a saved register)
      0xFF4B,                         # fmov.s fr4,@-r15
      0x60F6,                         # mov.l @r15+,r0
      0x000B, 0x0009]                 # rts / nop


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
        elif '*(int *)' not in out:
            bad.append('bits: the word is not read back as an int:\n%s' % out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] floatbits check failed:\n' + '\n'.join(bad))
    print('[floatbits] ok: a float popped into an integer register is read back as its bits')


if __name__ == '__main__':
    main()
