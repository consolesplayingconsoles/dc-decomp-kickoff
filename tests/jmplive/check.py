#!/usr/bin/env python3
"""Register liveness across a jmp to a constant inside the function (scripts/tools/5-generated/gen_equiv/gen_core.py reg_liveness).
No game data, no compiler. Stdlib only.

The flat form writes a register back before a goto only where it is live, and folds a load into its compare when the register is dead
after it. The liveness gave a jmp's delay slot no successor, so nothing was live after `mov.l @(pool),r2 / jmp @r2` even when the pool
constant is an address inside the function: cpuChasePlan (Virtua Tennis) loads a global into r0, tests it against 4, jumps to code that
tests the same r0 against 2; the C folded the load into the first test and the second read a stale R0.

    check.py      mov.l @r3,r0 / cmp/eq #4,r0 / bt / mov.l @(pool),r2 / jmp @r2 / nop / ... / T: cmp/eq #2,r0:
                    without   with no jump edges r0 is dead at the jmp (as it was)
                    with      with the jmp's edge to T, r0 is live at the jmp and at the cmp/eq #4 (it must be kept)
                    wired     gen_core passes the flat form's jump edges (GOTO) to both liveness passes
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '5-generated', 'gen_equiv')
sys.path[:0] = [GEN, os.path.join(GEN, '..'), os.path.join(GEN, '..', '..')]


def main():
    import tempfile
    os.chdir(tempfile.mkdtemp())             # gen_core reads the game's files when imported: stand-ins
    open('1ST_READ.BIN', 'wb').write(b'\x09\x00' * 64)
    open('BASE', 'w').write('8C010000\n')
    open('functions.txt', 'w').write('F 8c010000 128 stubfn\n')
    import gen_core
    ins = [('mov.l', '@r3,r0', 0x8C000000), ('cmp/eq', '#4,r0', 0x8C000002), ('bt', '0x8c00000e', 0x8C000004),
           ('mov.l', '@(0x8c000018,pc),r2 ; =8c000012', 0x8C000006), ('jmp', '@r2', 0x8C000008), ('nop', '', 0x8C00000A),
           ('nop', '', 0x8C00000C), ('rts', '', 0x8C00000E), ('mov', '#7,r0', 0x8C000010),
           ('cmp/eq', '#2,r0', 0x8C000012), ('rts', '', 0x8C000014), ('mov', '#3,r0', 0x8C000016)]
    addr2idx = {pc: i for i, (_, _, pc) in enumerate(ins)}
    bad = []
    try:
        without = gen_core.reg_liveness(ins, addr2idx)
        withj = gen_core.reg_liveness(ins, addr2idx, {4: [9]})
    except TypeError as e:
        sys.exit('[ERROR] jmplive check failed:\nwith: reg_liveness takes no jump edges (%s)' % e)
    if 'r0' in without.get(4, set()):
        bad.append('without: r0 live at the jmp with no edges (the case the fix is for no longer shows)')
    if 'r0' not in withj.get(4, set()) or 'r0' not in withj.get(2, set()):
        bad.append('with: r0 not live at the jmp (%s) or the bt (%s) with the jmp edge' % (sorted(withj.get(4, set())), sorted(withj.get(2, set()))))
    src = open(os.path.join(GEN, 'gen_core.py')).read()
    if len(re.findall(r'reg_liveness\(ins,addr2idx,GOTO\)', src)) < 2:
        bad.append('wired: gen_core does not pass GOTO to both liveness passes')
    if bad:
        sys.exit('[ERROR] jmplive check failed:\n' + '\n'.join(bad))
    print('[jmplive] ok: a register read after a jmp to a constant inside the function is live at the jmp')


if __name__ == '__main__':
    main()
