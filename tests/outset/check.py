#!/usr/bin/env python3
"""The result registers two runs are compared on (scripts/tools/equiv.py same, sh4sim.py out_set). Stdlib only, no compiler, no game data.

A function that returns on a path that leaves r0 as it came in hands its caller a leftover; the compiled C has no way to hand back the same
one (Virtua Tennis ballMarkCheck: the original branches to its epilogue on a flag and returns the entry r0, the C an unset local that came
out as a pointer; menuTextIconPut the same). A returned address in the stack is the frame layout's, as an argument's is (cpuBallPredict:
0DFFFEC8 against 0DFFFE9C).

    check.py      sim      a function that never assigns r0 reports out_set r0 False (the entry value is in out); one that does, True
                  call     a function whose only assignment of r0 is the result of a call out reports True
                  left     the comparison skips r0 when the original never assigned it, and keeps it when it did, and keeps fr0 either way
                  older    a run without out_set (stored before it existed) is compared on every register as before
                  stack    two different addresses in the stack are equal in a result register, two other different values are not
"""
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(SKILL, "scripts", "tools"))
import toolpath  # noqa: E402,F401
import sh4sim  # noqa: E402
import equiv  # noqa: E402

BASE = 0x0C010000


def run(words, regs, calls=None):
    code = struct.pack('<%dH' % len(words), *words)
    tmp = tempfile.mkdtemp()
    try:
        open(os.path.join(tmp, "1ST_READ.BIN"), "wb").write(code)
        case = {'exe': '1ST_READ.BIN', 'base': '%08X' % BASE, 'entry': '%08X' % BASE, 'end': '%08X' % (BASE + len(code)), 'regs': regs}
        if calls:
            case['calls'] = calls
        return sh4sim.run(case, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    bad = []
    keep = run([0x000B, 0x0009], {'r0': '00001234'})                        # rts / nop
    if keep.get('error') or keep['out']['r0'] != '00001234' or keep['out_set'] != {'r0': False}:
        bad.append('sim: a function that never assigns r0 gives %s %s' % (keep.get('out', {}).get('r0'), keep.get('out_set')))
    mov = run([0xE007, 0x000B, 0x0009], {'r0': '00001234'})                  # mov #7,r0 / rts / nop
    if mov.get('error') or mov['out']['r0'] != '00000007' or mov['out_set'] != {'r0': True}:
        bad.append('sim: a function that assigns r0 gives %s %s' % (mov.get('out', {}).get('r0'), mov.get('out_set')))
    # sts.l pr,@-r15 / mov.l @(pool),r3 / jsr @r3 / nop / lds.l @r15+,pr / rts / nop / pad / pool (0): the callee's result is r0
    call = run([0x4F22, 0xD303, 0x430B, 0x0009, 0x4F26, 0x000B, 0x0009, 0x0009, 0x0000, 0x0000], {'r0': '00001234'}, [{'r0': '00000055'}])
    if call.get('error') or call['out']['r0'] != '00000055' or call['out_set'] != {'r0': True}:
        bad.append('call: the result of a call out is not counted as assigned: %s %s %s' % (call.get('error'), call.get('out', {}).get('r0'), call.get('out_set')))

    def side(r0, fr0='00000000', out_set=None):
        d = {'out': {'r0': r0, 'r1': '00000000', 'fr0': fr0, 'fr1': '00000000'}, 'calls': [], 'writes': [], 'devices': []}
        if out_set is not None:
            d['out_set'] = out_set
        return d

    unset, assigned = {'r0': False}, {'r0': True}
    if not equiv.same(side('00000000', out_set=unset), side('0C810000'), ['r0'], {})[0]:
        bad.append('left: r0 the original never assigned is compared')
    if equiv.same(side('00000000', out_set=assigned), side('0C810000'), ['r0'], {})[0]:
        bad.append('left: r0 the original assigned is not compared')
    if equiv.same(side('00000000', fr0='3F800000', out_set=unset), side('00000000', fr0='00000000'), ['r0', 'fr0'], {})[0]:
        bad.append('left: fr0 is skipped when r0 is unassigned')
    if equiv.same(side('00000000'), side('0C810000'), ['r0'], {})[0]:
        bad.append('older: a run without out_set is not compared on r0')
    if not equiv.same(side('0DFFFEC8', out_set=assigned), side('0DFFFE9C'), ['r0'], {})[0]:
        bad.append('stack: two addresses in the stack differ')
    if equiv.same(side('0C810000', out_set=assigned), side('0C820000'), ['r0'], {})[0]:
        bad.append('stack: two other addresses are equal')
    if equiv.same(side('0DFFFEC8', out_set=assigned), side('0C820000'), ['r0'], {})[0]:
        bad.append('stack: an address in the stack equals one outside it')
    if not bad:
        print("[outset] ok: r0 the original never assigned is not compared, a call's result counts as assigned, older runs keep every register, a stack address in a result is the frame's")
        return
    sys.exit("[ERROR] outset check failed:\n" + "\n".join(bad))


if __name__ == '__main__':
    main()
