#!/usr/bin/env python3
"""A drawn case whose original reaches memory outside RAM at an address made from the stack is no case
(scripts/tools/5-generated/gen_equiv/gen_drv.py original_runs, stack_moved). No game data, no compiler. Stdlib only.

A function that touches hardware keeps cases with accesses outside RAM. One that reads a local table by an argument (rankDrawCharaIcon,
Virtua Tennis: a 72-byte table copied to its stack, read at table[a4]) gets a huge a4 from the drawing and reads far below its stack;
the address wraps out of RAM (1FFFFE3C) and is recorded as a device access. The table sits elsewhere in the C's frame, so the C reads
at 1FFFFE08: a difference no game input makes. Run again with the stack lower, such an access moves with it; a hardware register does not.

    check.py      stack_moved(devices of the run, devices of the run with the stack 0x300 lower, 0x300):
                    moved     an access whose address moved by exactly the shift: True
                    fixed     a hardware register read at the same address both times: False
                    above     an access just above the stack's top (0E000040: a table read past its end) that the lower run makes as an
                              ordinary read inside the stack (0DFFFD40, in its reads): True (kmProcessVertexRenderState, ndbEditShowEntry)
                    other     an access that moved by another amount: False (not this case; nothing is dropped)
                    mirror    an access in a mirror of main RAM (0D000000-0FFFFFFF, the simulator's stack aside) is a stray pointer the
                              game never makes (its pointers are 8C...): cpuSglAimTable read 0E6E76C4 and 0E6E7610, which the C read in
                              the other order, and those accesses are compared in order as a device's
                    unnamed   an access outside RAM in a 16 MB region the function's code names no address in is a stray pointer
                              (selCursorInput: a random word as a pointer read 103C3B4C, the C 1E29B898; FUN_8c0f8590, 14F01FCA...):
                              the case is dropped; one in a region it names (its hardware registers, VRAM) is kept
                    wired     original_runs asks it before keeping a case with accesses outside RAM
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
GEN = os.path.join(TOOLS, '5-generated', 'gen_equiv')


def main():
    src = open(os.path.join(GEN, 'gen_drv.py')).read()
    ns = {}
    try:
        exec(compile(src[src.index('def stack_moved('):src.index('\ndef ', src.index('def stack_moved(') + 5)], 'gen_drv.py', 'exec'), ns)
    except ValueError:
        sys.exit('[ERROR] wildstack check failed:\nmoved: gen_drv.py has no stack_moved()')
    f = ns['stack_moved']
    bad = []
    if f([['r', '1FFFFE3C', 4, '00000000']], [['r', '1FFFFB3C', 4, '00000000']], 0x300) is not True:
        bad.append('moved: an access that moved by the stack shift is not seen')
    if f([['w', '005F8040', 4, '00000001']], [['w', '005F8040', 4, '00000001']], 0x300) is not False:
        bad.append('fixed: a hardware register at the same address is taken for a stack address')
    if f([['r', '1FFFFE3C', 4, '00000000']], [['r', '1FFFFE00', 4, '00000000']], 0x300) is not False:
        bad.append('other: an access that moved by another amount is taken for a stack address')
    if f([['r', '0E000040', 4, '00000000']], [], 0x300, [0x0DFFFD40]) is not True:
        bad.append('above: an access above the stack that the lower run reads inside it is not seen')
    if f([['r', '1FFFFE3C', 4, '00000000']], [], 0x300, [0x0C800000]) is not False:
        bad.append('other: an access the lower run does not make anywhere is taken for a stack address')
    try:
        ns2 = {}
        exec(compile(src[src.index('def ram_mirror('):src.index('\ndef ', src.index('def ram_mirror(') + 5)], 'gen_drv.py', 'exec'), ns2)
        rm = ns2['ram_mirror']
        if rm([['r', '0E6E7610', 4, '00000000']], 0x0E000000) is not True:
            bad.append('mirror: a read in a RAM mirror is not seen')
        if rm([['w', '005F8040', 4, '00000001'], ['r', '1FFFFE3C', 4, '0']], 0x0E000000) is not False:
            bad.append('mirror: a hardware register is taken for a RAM mirror')
        if rm([['r', '0DFFFF40', 4, '0']], 0x0E000000) is not False:
            bad.append('mirror: the simulator\'s stack is taken for a RAM mirror')
    except ValueError:
        bad.append('mirror: gen_drv.py has no ram_mirror()')
    if 'ram_mirror(' not in src[src.index('def original_runs('):src.index('def grow(')]:
        bad.append('wired: original_runs does not ask ram_mirror')
    try:
        ns3 = {}
        exec(compile(src[src.index('def unnamed_region('):src.index('\ndef ', src.index('def unnamed_region(') + 5)], 'gen_drv.py', 'exec'), ns3)
        ur = ns3['unnamed_region']
        named = {0xA05F8000 & 0x1FFFFFFF}
        if ur([['r', '1CA369BC', 4, '0']], named) is not True:
            bad.append('unnamed: an access in a region the function never names is kept')
        if ur([['w', '005F8040', 4, '1'], ['r', '005F6900', 4, '0']], named) is not False:
            bad.append('unnamed: an access in the region of a named register is dropped')
    except ValueError:
        bad.append('unnamed: gen_drv.py has no unnamed_region()')
    if 'unnamed_region(' not in src[src.index('def original_runs('):src.index('def grow(')]:
        bad.append('wired: original_runs does not ask unnamed_region')
    if 'stack_moved(' not in src[src.index('def original_runs('):src.index('def grow(')]:
        bad.append('wired: original_runs does not ask stack_moved')
    if bad:
        sys.exit('[ERROR] wildstack check failed:\n' + '\n'.join(bad))
    print('[wildstack] ok: a case reaching outside RAM through the stack is dropped; hardware accesses are kept')


if __name__ == '__main__':
    main()
