#!/usr/bin/env python3
"""Which argument registers a callee reads, as a set (scripts/tools/5-generated/gen_equiv/gen_core.py entry_reads_of), and the call
comparison that uses it (scripts/tools/equiv.py callview). No game data, no compiler. Stdlib only.

callee_arity counts up to the highest register a function reads: cpuShotRange (Virtua Tennis) reads fr6-fr10 after a call, counts 7
floats and so takes in fr4 and fr5; cpuSglAimScore's generated C names fr4 and fr5 only to pass them on, and its caller
cpuSglPickLv07 was compared on a leftover fr5 (1.0 in the original, 5 in the C) and dropped from 100%.

    check.py      instruction lists as gen_core reads them:
                    passon    fr4/fr5 untouched up to a call (target loaded 9 instructions before the jsr) to a callee that reads fr6
                              only: the function reads fr6, not fr4 or fr5
                    clobber   a float read after a call is not read at the entry (the call writes fr0-fr11)
                    unknown   a jmp out of the function (a tail call) or frchg: not known (None), nothing is masked
                    masked    callview compares a call only on the registers its callee's original reads; the rest show as *
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
GEN = os.path.join(TOOLS, '5-generated', 'gen_equiv')
sys.path[:0] = [GEN, os.path.join(GEN, '..'), TOOLS]


def main():
    os.chdir(tempfile.mkdtemp())             # gen_core reads the game's files when imported: stand-ins
    open('1ST_READ.BIN', 'wb').write(b'\x09\x00' * 64)
    open('BASE', 'w').write('8C010000\n')
    open('functions.txt', 'w').write('F 8c010000 128 stubfn\n')
    import gen_core
    bad = []
    if not hasattr(gen_core, 'entry_reads_of'):
        sys.exit('[ERROR] entryreads check failed:\ngen_core has no entry_reads_of')
    pc = [0x8C000000 + 2 * k for k in range(40)]
    a = [('mov.l', '@(0x8c000060,pc),r3 ; =8c000100 calleeB', pc[0])]
    a += [('mov', '#%d,r1' % k, pc[1 + k]) for k in range(8)]                 # 8 instructions between the load and the jsr
    a += [('mov', 'r4,r14', pc[9]), ('jsr', '@r3', pc[10]), ('nop', '', pc[11]), ('fmov', 'fr0,fr1', pc[12]),
          ('rts', '', pc[13]), ('nop', '', pc[14])]
    reads = {'calleeB': frozenset(['fr6'])}
    got = gen_core.entry_reads_of(a, lambda n: reads.get(n))
    if got is None or 'fr4' in got or 'fr5' in got or 'fr6' not in got or 'r4' not in got:
        bad.append('passon: entry reads %s, want r4 and fr6, not fr4/fr5' % (sorted(got) if got is not None else None))
    b = [('mov.l', '@(0x8c000060,pc),r3 ; =8c000100 calleeC', pc[0]), ('jsr', '@r3', pc[1]), ('nop', '', pc[2]),
         ('fmov', 'fr4,fr0', pc[3]), ('rts', '', pc[4]), ('nop', '', pc[5])]
    got = gen_core.entry_reads_of(b, lambda n: frozenset())
    if got is None or 'fr4' in got:
        bad.append('clobber: fr4 read after a call counts as read at the entry (%s)' % (sorted(got) if got is not None else None))
    c = [('mov.l', '@(0x8c000060,pc),r3 ; =8c000100 calleeD', pc[0]), ('jmp', '@r3', pc[1]), ('nop', '', pc[2])]
    d = [('frchg', '', pc[0]), ('fmov', 'fr4,fr0', pc[1]), ('rts', '', pc[2]), ('frchg', '', pc[3])]
    for name, ins in (('tail call', c), ('frchg', d)):
        if gen_core.entry_reads_of(ins, lambda n: frozenset()) is not None:
            bad.append('unknown: a %s gives a set, not None' % name)
    import equiv
    equiv._READS[0x0C000100] = (frozenset([4]), frozenset([6]))
    v = equiv.callview('0C000100', ['00000001', '00000002'], ['3F800000', '40000000', '40400000'], {0x0C000100: (2, 3)})
    if v[1][:2] != ['00000001', '*'] or v[2] != ['*', '*', '40400000']:
        bad.append('masked: callview gives %s %s, want r4 and fr6 only' % (v[1], v[2]))
    equiv._READS[0x0C000200] = None
    v = equiv.callview('0C000200', ['00000001', '00000002'], ['3F800000'], {0x0C000200: (2, 1)})
    if v[1][:2] != ['00000001', '00000002'] or v[2] != ['3F800000']:
        bad.append('masked: an unknown callee lost registers (%s %s)' % (v[1], v[2]))
    if bad:
        sys.exit('[ERROR] entryreads check failed:\n' + '\n'.join(bad))
    print('[entryreads] ok: a register passed on untouched to a callee that does not read it is not read; a call writes the floats; '
          'a tail call or frchg is not known; a call is compared on what its callee reads')


if __name__ == '__main__':
    main()
