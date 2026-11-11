#!/usr/bin/env python3
"""A piece of a function listed as a function of its own (scripts/tools/1-2-baseline/checksizes.py --merge, frame_piece;
scripts/tools/5-generated/gen_equiv/gen_core.py frame_piece). Zombie Revenge FUN_0c0b954e is the end of FUN_0c0b8bcc: the parent
reaches it by `bra`, and it stores into and closes the parent's 28-byte frame. The generator wrote the branch as a call; the C
parent's frame is 120 bytes, so the piece's epilogue popped a local into pr and the game ran its heap after a character was
picked. The proofs passed: a call is stubbed, the piece never ran inside the C's frame. No game data, no compiler. Stdlib only.

    check.py      merge      checksizes.py --merge --write takes the piece into the function that branches into it
                  tail       a function that branches to a real function (it opens its own frame) is not merged
                  refuse     the generator does not write the branch into the piece as a call: it skips the parent and says why
                  call       the generator still writes the branch to the real function as a tail call
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
W = lambda *h: struct.pack('<%dH' % len(h), *h)

CODE = (W(0x4F22, 0x7FF8, 0x2448, 0x8903, 0x7F08, 0x4F26, 0x000B, 0x0009) +   # 0 parent: sts.l pr / add #-8 / tst r4 / bt 16 / add #8 / lds pr / rts / nop
        W(0x1F41, 0x7F08, 0x4F26, 0x000B, 0x0009, 0x0009) +                    # 16 piece: mov.l r4,@(4,r15) / add #8 / lds.l @r15+,pr / rts / nop / pad
        W(0x4F22, 0x7FFC, 0x7F04, 0x4F26, 0x000B, 0x0009) +                    # 28 real: sts.l pr / add #-4 / add #4 / lds pr / rts / nop
        W(0xAFF8, 0x0009))                                                     # 40 tailer: bra 28 (real) / nop
FUNCS = 'F 0c010000 16 parent\nF 0c010010 12 piece\nF 0c01001c 12 real\nF 0c010028 4 tailer\n'


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(CODE)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write(FUNCS)
        os.makedirs(os.path.join(tmp, 'src'))
        # the generator first, on the split listing: the parent is refused, the tailer is written
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv, gen_pipe\n"
                  "for n in sys.argv[1:]:\n"
                  "    try:\n"
                  "        print('@@@@ ' + n); print(gen_drv.build(n, gen_pipe.variants(n, False)[0], False)[0])\n"
                  "    except gen_core.Skip as e:\n"
                  "        print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script, 'parent', 'tailer'], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True, env=dict(os.environ, GEN_FRAME='0')).stdout
        parts = {c.split('\n', 1)[0]: c.split('\n', 1)[1] if '\n' in c else '' for c in out.split('@@@@ ')[1:]}
        if 'SKIPPED' not in parts.get('parent', '') or 'piece' not in parts.get('parent', ''):
            bad.append('refuse: the parent should be skipped naming the piece, got:\n' + parts.get('parent', out[-400:]))
        if 'SKIPPED' in parts.get('tailer', 'SKIPPED') or 'real(' not in parts.get('tailer', ''):
            bad.append('call: the branch to a real function should be a tail call, got:\n' + parts.get('tailer', out[-400:]))
        r = subprocess.run([sys.executable, 'tools/1-2-baseline/checksizes.py', '--merge', '--write'], cwd=tmp,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        sizes = {l.split()[3]: int(l.split()[2]) for l in open(os.path.join(tmp, 'functions.txt')) if l.startswith('F ')}
        if sizes.get('parent') != 28 or 'piece' in sizes:
            bad.append('merge: want parent 28 bytes and no piece entry, got %r (%s)' % (sizes, r.stdout.strip()[-300:]))
        if sizes.get('real') != 12 or sizes.get('tailer') != 4:
            bad.append('tail: real and tailer should stay 12 and 4, got %r' % sizes)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for b in bad:
        print('FAIL', b)
    print('framepiece: %s' % ('OK' if not bad else '%d failures' % len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
