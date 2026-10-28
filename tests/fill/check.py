#!/usr/bin/env python3
"""What a mocked call writes through its argument registers (scripts/tools/sh4sim.py poke_arg), with the real simulator on synthetic
code. No game data, no compiler. Stdlib only.

A case answers a call with words the callee writes through an argument register (an output buffer). The register may hold a value,
not an address: Virtua Tennis angDiff(int a4, int a5) takes two angles, and with a4 = 0 the fill went to address 0 on whichever side
had 0 there, so the two sides of a check saw different memory (playerPut, call 80).

    check.py      f(r4) answered with a fill through r4, then *r4 read back:
                    value    r4 = 0: nothing is written, the word read back is not the fill
                    address  r4 = a RAM address: the fill is there
                  f() answered with a fill through the word at SP (poke_stack, a structure returned by value), a RAM address
                  pushed there, read back:
                    nostack  stackfill says the callee takes no stack word and returns no structure: nothing is written (playerPut ->
                             angDiff, Virtua Tennis: the address at SP was the caller's own local, filled on the original's side only)
                    stack    stackfill not given, or says yes: the fill is there
                  f(r5) twice, r5 set before the first call only, then *r5 read back:
                    leftover the fill answering the second call is not made: r5 there is a leftover, not an argument (circuitDrawMatchInfo
                             -> sprSheetPut, Virtua Tennis: the original's leftover r5 was an object pointer and got the fill, the C's
                             leftover was elsewhere)
                    set      the fill answering the first call, which r5 was set for, is made
                    stackleft  the word at SP pushed before the first call only: the fill answering the second call is not made (a
                             leftover, as for registers: endingSceneDraw, Virtua Tennis, a leftover word 8C125E09 at SP got a fill one byte
                             into a table of the game's own data)
                    stackvalue  the word at SP is a small value, not an address: nothing is written to low memory (playerPut case 4:
                             the C's word at SP was a value, the fill went to page 0, and a later read through a small pointer saw it
                             on the C's side only)
"""
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
sys.path[:0] = [TOOLS]
import toolpath  # noqa: E402,F401
import sh4sim  # noqa: E402

BASE = 0x8C010000


def program(first):
    code = [0x4F22,              # sts.l pr,@-r15
            first,               # r4 = 0, or r4 = a RAM address from the pool
            0xB004,              # bsr f (outside the function)
            0x0009,              # nop
            0x6042,              # mov.l @r4,r0
            0x4F26,              # lds.l @r15+,pr
            0x000B, 0x0009,      # rts / nop
            0x000B, 0x0009]      # f: rts / nop
    body = b''.join(struct.pack('<H', w) for w in code) + struct.pack('<I', BASE + 0x100)
    return body + b'\x00' * (0x200 - len(body))


def main():
    bad = []
    d = tempfile.mkdtemp()
    try:
        case = {'calls': [{'r0': '00000000', 'poke_arg': {'r4': '11111111'}}]}
        for name, first, want in (('value', 0xE400, False), ('address', 0xD404, True)):
            open(os.path.join(d, name + '.bin'), 'wb').write(program(first))
            r = sh4sim.run(dict(case, exe=name + '.bin', base='%08X' % BASE, entry='%08X' % BASE, end='%08X' % (BASE + 0x10),
                                steps=2000), d)
            got = r['out']['r0'] == '11111111'
            if got != want:
                bad.append('%s: the word read back is %s (%s)' % (name, r['out']['r0'], r['error']))
        code = [0x4F22, 0xD205,      # sts.l pr / mov.l @(pool),r2   ; a RAM address
                0x2F26,              # mov.l r2,@-r15                ; at SP
                0xB005, 0x0009,      # bsr f / nop
                0x6022,              # mov.l @r2,r0
                0x7F04, 0x4F26,      # add #4,r15 / lds.l @r15+,pr
                0x000B, 0x0009,      # rts / nop
                0x000B, 0x0009]      # f: rts / nop
        body = b''.join(struct.pack('<H', w) for w in code) + struct.pack('<I', BASE + 0x100)
        open(os.path.join(d, 'stk.bin'), 'wb').write(body + b'\x00' * (0x200 - len(body)))
        case = {'calls': [{'r0': '00000000', 'poke_stack': '22222222'}]}
        for name, sf, want in (('nostack', lambda t: False, False), ('stack', None, True), ('stackyes', lambda t: True, True)):
            r = sh4sim.run(dict(case, exe='stk.bin', base='%08X' % BASE, entry='%08X' % BASE, end='%08X' % (BASE + 0x14), steps=2000),
                           d, stackfill=sf)
            if (r['out']['r0'] == '22222222') != want:
                bad.append('%s: the word read back is %s (%s)' % (name, r['out']['r0'], r['error']))
        code = [0x4F22, 0xD505,      # sts.l pr / mov.l @(pool),r5   ; a RAM address
                0xB006, 0x0009,      # bsr f / nop
                0xB004, 0x0009,      # bsr f / nop                   ; r5 not set again: a leftover
                0x6052,              # mov.l @r5,r0
                0x4F26, 0x000B, 0x0009,      # lds.l @r15+,pr / rts / nop
                0x000B, 0x0009]      # f: rts / nop
        body = b''.join(struct.pack('<H', w) for w in code) + struct.pack('<I', BASE + 0x100)
        open(os.path.join(d, 'left.bin'), 'wb').write(body + b'\x00' * (0x200 - len(body)))
        for name, calls, want in (('leftover', [{'r0': '00000000'}, {'r0': '00000000', 'poke_arg': {'r5': '33333333'}}], False),
                                  ('set', [{'r0': '00000000', 'poke_arg': {'r5': '33333333'}}, {'r0': '00000000'}], True)):
            r = sh4sim.run({'calls': calls, 'exe': 'left.bin', 'base': '%08X' % BASE, 'entry': '%08X' % BASE, 'end': '%08X' % (BASE + 0x14),
                            'steps': 2000}, d)
            if (r['out']['r0'] == '33333333') != want:
                bad.append('%s: the word read back is %s (%s)' % (name, r['out']['r0'], r['error']))
        code = [0x4F22, 0xD206,      # sts.l pr / mov.l @(pool),r2   ; a RAM address
                0x2F26,              # mov.l r2,@-r15                ; at SP, once
                0xB007, 0x0009,      # bsr f / nop
                0xB005, 0x0009,      # bsr f / nop                   ; the word at SP not written again
                0x6022,              # mov.l @r2,r0
                0x7F04, 0x4F26,      # add #4,r15 / lds.l @r15+,pr
                0x000B, 0x0009,      # rts / nop
                0x000B, 0x0009]      # f: rts / nop
        body = b''.join(struct.pack('<H', w) for w in code) + struct.pack('<I', BASE + 0x100)
        open(os.path.join(d, 'stkl.bin'), 'wb').write(body + b'\x00' * (0x200 - len(body)))
        r = sh4sim.run({'calls': [{'r0': '00000000'}, {'r0': '00000000', 'poke_stack': '44444444'}], 'exe': 'stkl.bin', 'base': '%08X' % BASE,
                        'entry': '%08X' % BASE, 'end': '%08X' % (BASE + 0x18), 'steps': 2000}, d)
        if r['out']['r0'] == '44444444':
            bad.append('stackleft: the fill through a leftover word at SP was made (%s)' % r['error'])
        code = [0x4F22, 0xE210,      # sts.l pr / mov #16,r2   ; a value
                0x2F26,              # mov.l r2,@-r15          ; at SP
                0xB005, 0x0009,      # bsr f / nop
                0x6022,              # mov.l @r2,r0            ; low memory
                0x7F04, 0x4F26,      # add #4,r15 / lds.l @r15+,pr
                0x000B, 0x0009,      # rts / nop
                0x000B, 0x0009]      # f: rts / nop
        body = b''.join(struct.pack('<H', w) for w in code)
        open(os.path.join(d, 'stkv.bin'), 'wb').write(body + b'\x00' * (0x200 - len(body)))
        r = sh4sim.run(dict(case, exe='stkv.bin', base='%08X' % BASE, entry='%08X' % BASE, end='%08X' % (BASE + 0x14), steps=2000), d)
        if r['out']['r0'] == '22222222':
            bad.append('stackvalue: the fill went to address 0x10 (%s)' % r['error'])
    finally:
        shutil.rmtree(d, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] fill check failed:\n' + '\n'.join(bad))
    print('[fill] ok: a mocked call fills through an argument register only when it was set for the call and holds a RAM address, and through the word at SP only for a callee that can write there')


if __name__ == '__main__':
    main()
