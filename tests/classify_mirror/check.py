#!/usr/bin/env python3
"""A function that runs the rest of itself from another mirror of its own code (scripts/tools/5-generated/classify.py,
self_mirror_jump). The SDK's cache flush (Zombie Revenge FUN_0c22b324, FUN_0c2113b4) takes the address of its next block with mova,
ORs it with A0000000 and jumps there: the rest runs uncached on the same frame, which C cannot ask for. Listed as two functions, the
second was a piece that pops a word it never pushed. A jump through a mirror to another function (syHwCacheFinish -> p2_cache_set) is a
call C can make. No game data. Stdlib only.

    check.py      selfmirror   mova + or A0000000 + jmp into its own span:              no C form, names the mirrored address
                  split        the same code listed only up to the jump:                not flagged by this rule (nothing of its own)
                  mirrorcall   or A0000000 + jmp to the function after it:              not flagged
"""
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '5-generated'))
import classify  # noqa: E402

BASE = 0x0C010000
NOP, RTS = 0x0009, 0x000B


def words(*ws):
    return b''.join(struct.pack('<H', w) for w in ws)


def main():
    a = BASE
    selfmirror = words(0x7FFC,            # +0  add #-4,r15
                       0xC703,            # +2  mova @(+10),r0        its own next block
                       0xD101,            # +4  mov.l @(+C),r1        A0000000
                       0x210B,            # +6  or r0,r1
                       0x412B,            # +8  jmp @r1
                       NOP,               # +A
                       0x0000, 0xA000,    # +C  A0000000
                       RTS, 0x7F04)       # +10 rts / add #4,r15: pops the word +0 pushed
    b = a + len(selfmirror)
    mirrorcall = words(0xD302,            # +0  mov.l @(+C),r3        A0000000
                       0xD403,            # +2  mov.l @(+10),r4       the next function
                       0x243B,            # +4  or r3,r4
                       0x442B,            # +6  jmp @r4
                       NOP, NOP,          # +8
                       0x0000, 0xA000)    # +C  A0000000
    c = b + len(mirrorcall) + 4
    mirrorcall += struct.pack('<I', c)    # +10 the next function's address
    other = words(RTS, NOP)
    exe = selfmirror + mirrorcall + other

    tmp = tempfile.mkdtemp(prefix='classify_mirror_')
    here = os.getcwd()
    try:
        os.chdir(tmp)
        open('functions.txt', 'w').write('F %08x %d selfmirror\nF %08x %d mirrorcall\nF %08x %d other\n'
                                         % (a, len(selfmirror), b, c - b, c, len(other)))
        check(exe, a, b, c, len(selfmirror))
    finally:
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)
    print('[classify_mirror] ok: code that runs the rest of itself from another mirror is no C form; a mirrored call to another function is not')


def check(exe, a, b, c, size):
    got = classify.self_mirror_jump(exe, BASE, a, size)
    assert got == (0xA0000000 | (a + 0x10)), 'selfmirror: the jump to its own uncached code is not found (%r)' % got
    why = classify.no_c_form(exe, BASE, a, size)
    assert any('mirror' in w for w in why), 'selfmirror is not no C form: %r' % why
    assert classify.self_mirror_jump(exe, BASE, a, 0x10) is None, 'split: a jump past its own end is flagged as its own code'
    assert classify.self_mirror_jump(exe, BASE, b, c - b) is None, 'mirrorcall: a jump to another function through a mirror is flagged'


main()
