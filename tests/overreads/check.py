#!/usr/bin/env python3
"""What tools/5-generated/overreads.py does to the simulator's memory, with no game data and no compiler. Stdlib only.

    check.py      two hand-assembled SH-4 functions, one reading the word at r4 and one the word at r4+4 (the wrong struct field):
                    zeros     on plain memory both return 0, so equiv.py cannot tell them apart
                    junk      on junk memory they return different values (the over-read shows)
                    stable    the same code on junk twice returns the same value (a run is repeatable)
                    poked     a word the case set is read as set, not as junk
                    stack     the stack stays zero (a local nobody wrote is not an over-read)
                    restored  sh4sim.Memory is the plain class again afterwards
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(SKILL, 'scripts', 'tools'))
sys.path.insert(0, os.path.join(SKILL, 'scripts', 'tools', '5-generated'))
import sh4sim  # noqa: E402
import overreads  # noqa: E402

AT = 0x0C010000
READ_FIELD0 = bytes([0x40, 0x50, 0x0B, 0x00, 0x09, 0x00])     # mov.l @(0,r4),r0 ; rts ; nop
READ_FIELD1 = bytes([0x41, 0x50, 0x0B, 0x00, 0x09, 0x00])     # mov.l @(4,r4),r0 ; rts ; nop
STRUCT = '0C100000'


def r0(code, case, junk):
    real = sh4sim.run
    if junk:
        res = overreads.run_with_junk(real, case, '.', (AT, code))
    else:
        res = real(case, '.', (AT, code))
    assert not res['error'], res['error']
    return res['out']['r0']


def main():
    case = {'regs': {'r4': STRUCT}}
    bad = []
    a0, a1 = r0(READ_FIELD0, case, False), r0(READ_FIELD1, case, False)
    if a0 != a1 or a0 != '00000000':
        bad.append('zeros: %s vs %s, want both 00000000' % (a0, a1))
    j0, j1 = r0(READ_FIELD0, case, True), r0(READ_FIELD1, case, True)
    if j0 == j1 or j0 == '00000000':
        bad.append('junk: field 0 %s, field 1 %s, want two different non-zero values' % (j0, j1))
    if r0(READ_FIELD0, case, True) != j0:
        bad.append('stable: a second run on junk returned another value')
    poked = dict(case, poke={STRUCT: 'EFBEADDE'})
    got = r0(READ_FIELD0, poked, True)
    if got != 'DEADBEEF':
        bad.append('poked: read %s, want DEADBEEF' % got)
    # the stack: a function reading the word at its own stack pointer, which nothing wrote, must see 0 even on junk
    stack_read = bytes([0xF3, 0x61, 0x12, 0x60, 0x0B, 0x00, 0x09, 0x00])   # mov r15,r1 ; mov.l @r1,r0 ; rts ; nop
    got = r0(stack_read, {}, True)
    if got != '00000000':
        bad.append('stack: read %s from an unwritten stack word, want 00000000' % got)
    if sh4sim.Memory.__name__ != 'Memory':
        bad.append('restored: sh4sim.Memory is %s' % sh4sim.Memory.__name__)
    if bad:
        print('FAIL\n  ' + '\n  '.join(bad))
        return 1
    print('ok: zeros, junk, stable, poked, stack, restored')
    return 0


if __name__ == '__main__':
    sys.exit(main())
