#!/usr/bin/env python3
"""A word read at SP after a frame was made below pushed words is the frame's, not a pushed one
(scripts/tools/5-generated/gen_equiv/gen_core.py, the reload of a pending push). No game data, no compiler. Stdlib only.

A read at @(d,r15) while pushed words were pending was taken as the push d bytes up, even when an add to r15 had made a frame below
them: a function with a second prologue inside it (registers pushed, then a 28-byte frame) read its own loop counter as a saved
register's value (Zombie Revenge FUN_0c0658f0: a row number came out 0x2C on every pass, from the 0x100 in a pushed r8).

    check.py      a function that pushes r4, makes an 8-byte frame, stores 5 at SP and reads SP back into r0:
                    frame     the C returns 5 (the frame word), not a4 (the pushed word)
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

FN = [0x4F22,                       # sts.l pr,@-r15
      0xE300,                       # mov #0,r3 (the prologue ends)
      0x2F46,                       # mov.l r4,@-r15
      0x7FF8,                       # add #-8,r15
      0xE105,                       # mov #5,r1
      0x2F12,                       # mov.l r1,@r15
      0x60F2,                       # mov.l @r15,r0
      0x7F0C,                       # add #12,r15
      0x4F26,                       # lds.l @r15+,pr
      0x000B, 0x0009]               # rts / nop


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        code = W(FN) + (W([0x0009]) if len(FN) % 2 else b'')
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
        elif 'a4' in out.split('{', 1)[1]:
            bad.append('frame: the C reads the pushed a4 back, not the frame word:\n%s' % out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] pendgap check failed:\n' + '\n'.join(bad))
    print('[pendgap] ok: a read at SP below a made frame is the frame word')


if __name__ == '__main__':
    main()
