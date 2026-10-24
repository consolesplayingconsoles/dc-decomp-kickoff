#!/usr/bin/env python3
"""A tail jump into a runtime helper the checker runs (scripts/tools/sh4sim.py, `deep`): the helper runs to its return like one
reached by a call, and its own branches are not calls out. Stdlib only, no compiler.

    check.py      a two-function image: a helper that branches inside itself and returns 5, and a function that tail-jumps
                  to it (mov.l / jmp @r3), run with `deep` accepting the helper: no call out, r0 = 5 (strcmp -> _slow_strcmp1,
                  Crazy Taxi: the C's `return _slow_strcmp1(a, b);` compiles to jmp, and the helper's branch to its byte loop
                  was logged as a call, so the result came back as a mocked 0 / 4 instead of the comparison)
"""
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(SKILL, "scripts", "tools"))
import sh4sim  # noqa: E402

BASE = 0x0C010000
HELPER = BASE                  # bra +8 (to HELPER+8) / nop / nop / nop / rts / mov #5,r0 / nop / nop
FUNC = BASE + 0x10             # mov.l @(4,pc),r3 / jmp @r3 / nop / nop / .long HELPER


def main():
    helper = [0xA002, 0x0009, 0x0009, 0x0009, 0x000B, 0xE005, 0x0009, 0x0009]
    func = [0xD301, 0x432B, 0x0009, 0x0009] + list(struct.unpack('<2H', struct.pack('<I', HELPER)))
    tmp = tempfile.mkdtemp()
    try:
        words = helper + func
        open(os.path.join(tmp, "1ST_READ.BIN"), "wb").write(struct.pack('<%dH' % len(words), *words))
        case = {'exe': '1ST_READ.BIN', 'base': '%08X' % BASE, 'entry': '%08X' % FUNC, 'end': '%08X' % (FUNC + 12)}
        r = sh4sim.run(case, tmp, deep=lambda t: t == HELPER)
        bad = []
        if r.get('error'):
            bad.append('error: %s' % r['error'])
        if r.get('calls'):
            bad.append('the helper\'s own branch is a call out: %s' % [c['to'] for c in r['calls']])
        if (r.get('out') or {}).get('r0') != '00000005':
            bad.append('r0 is %s, want 00000005' % (r.get('out') or {}).get('r0'))
        if not bad:
            print("[tailjump] ok: a tail jump into a runtime helper runs it to its return, its branches are not calls out")
            return
        sys.exit("[ERROR] tailjump check failed:\n" + "\n".join(bad))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
