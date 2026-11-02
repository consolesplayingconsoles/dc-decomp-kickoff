#!/usr/bin/env python3
"""A branch in a callback entry that no walk from a function's start reaches (scripts/tools/1-2-baseline/symbolize.py branches()).
No game data, no compiler. Stdlib only.

A callback pointer can name an address a few bytes past a listed function's end (Virtua Tennis: the file system's interrupt callback,
14 bytes after FUN_8c1dd692, a `bra` to gdFsExecServerG). The walk from the function's entry stops at its `jmp @r3` and never sees
it, so the branch stayed the original word and, once the two pieces were moved by different amounts, landed 32 bytes before
gdFsExecServerG, in padding: the game crashed on the first vblank after the file system was initialised.

    check.py      f1 = jmp @r3 / nop (listed, 4 bytes), then at +4 an entry the data piece's pointer names: bra f2 / nop; f2 at +20:
                    mid       the bra at +4 is written BRA _f2 (the linker relocates it), not the raw word
                    entry     f1's own walk is unchanged: its jmp stays a word
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
L = lambda *v: struct.pack('<%dI' % len(v), *v)

IMAGE = (W(0x432B, 0x0009) +                       # 00 f1: jmp @r3 / nop (listed size 4)
         W(0xA00C, 0x0009) +                        # 04 a callback entry (not a listed function): bra 20 (f2) / nop
         W(*([0x0009] * 12)) +                      # 08..1F padding
         W(0x000B, 0x0009) +                        # 20 f2: rts / nop
         W(*([0x0009] * 6)) +                       # 24..2F
         L(0x0C010004) +                            # 30 a pointer word that names the callback entry
         L(0, 0, 0))                                # 34..3F


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(IMAGE)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'layout.txt'), 'w').write('game 0C010000 0C010040\nfixed 0C010400\n')
        fl = 'F %08x 4 f1\nD %08x 0 pad\nF %08x 4 f2\nD %08x 0 ptrs\n' % (BASE, BASE + 0x08, BASE + 0x20, BASE + 0x30)
        open(os.path.join(tmp, 'report.txt'), 'w').write(fl)
        run = lambda *a: subprocess.run([sys.executable] + list(a), cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        universal_newlines=True).stdout
        out = run('tools/1-2-baseline/split_asm.py', '1ST_READ.BIN', '%08X' % BASE, 'report.txt', '.')
        out += run('tools/1-2-baseline/pointers.py')
        out += run('tools/1-2-baseline/symbolize.py', 'sym')
        get = lambda f: open(os.path.join(tmp, 'sym', 'asm', f)).read() if os.path.exists(os.path.join(tmp, 'sym', 'asm', f)) else ''
        f1 = get('0c010000_f1.src')
        if 'BRA         _f2' not in f1:
            bad.append('mid: the bra in the callback entry (+4) is not written BRA _f2:\n' + f1)
        if ".DATA.W     H'432B" not in f1:
            bad.append('entry: the jmp of f1 itself is no longer a word:\n' + f1)
        if bad:
            bad.append(out[-800:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] symbolize_mid check failed:\n' + '\n'.join(bad))
    print('[symbolize_mid] ok: a branch in a callback entry past the listed end is a name, so it follows its target when the pieces move')


if __name__ == '__main__':
    main()
