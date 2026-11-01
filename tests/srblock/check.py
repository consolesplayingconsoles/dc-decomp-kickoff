#!/usr/bin/env python3
"""ldc sr and the SR block bit (scripts/tools/sh4sim.py set_sr). Stdlib only, no compiler, no game data.

The simulator has no exceptions and no interrupts, so SR.BL (bit 28, "block exceptions") changes nothing it could show: a function that
sets it (stc sr / or #0x10000000 / ldc sr) must run, and `stc sr` must read the bit back. SR.RB (bit 29, register bank) selects a bank of
r0-r7 the simulator does not have: a function that changes it must still stop with an error. Virtua Tennis FUN_8c0f8100 (the interrupt
setup) was stuck as "not drawn: the original stopped: ldc sr changes the register bank or the block bit (not modelled)" for the BL bit alone.

    check.py      f: stc sr,r3 / mov.l @(pool),r2 / or r2,r3 / ldc r3,sr / stc sr,r0 / rts, run twice with the pool word set to
                    BL    0x10000000: runs, r0 = 0x50000000 (MD, BL)
                    RB    0x20000000: stops with the register bank error
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


def run(tmp, mask):
    words = [0x0302, 0xD203, 0x232B, 0x430E, 0x0002, 0x000B, 0x0009, 0x0009]    # stc sr,r3 / mov.l @(12,pc),r2 / or r2,r3 / ldc r3,sr / stc sr,r0 / rts / nop / pad
    code = struct.pack('<8H', *words) + struct.pack('<I', mask)
    open(os.path.join(tmp, "1ST_READ.BIN"), "wb").write(code)
    case = {'exe': '1ST_READ.BIN', 'base': '%08X' % BASE, 'entry': '%08X' % BASE, 'end': '%08X' % (BASE + 16)}
    return sh4sim.run(case, tmp)


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        r = run(tmp, 0x10000000)
        if r.get('error'):
            bad.append('BL: stopped: %s' % r['error'])
        elif (r.get('out') or {}).get('r0') != '50000000':
            bad.append('BL: r0 is %s, want 50000000' % (r.get('out') or {}).get('r0'))
        r = run(tmp, 0x20000000)
        if not r.get('error') or 'register bank' not in r['error']:
            bad.append('RB: no register bank error (%r)' % (r.get('error'),))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if not bad:
        print("[srblock] ok: ldc sr sets the block bit and reads it back, a register bank change still stops")
        return
    sys.exit("[ERROR] srblock check failed:\n" + "\n".join(bad))


if __name__ == '__main__':
    main()
