#!/usr/bin/env python3
"""A device register gives back what was last written to it (scripts/tools/sh4sim.py Memory). No game data, no compiler. Stdlib only.

The SDK's sys_init writes 8201 to the DMAC's DMAOR (FFA00040), reads it back and retries, 0x10000 counts a time, until it matches:
with every unscripted device read answering 0 the boot never left that loop in the simulator, and every boot comparison stopped
there (Virtua Tennis and Crazy Taxi, 2026-11-01). A value a case scripts (device_reads) still comes first.

    check.py      latch     write 8201 to FFA00040, read it: 8201
                  script    with a scripted read list, the scripted value comes back first, then the latched one
                  fresh     a register never written reads 0
                  hw_model  opt-in: SPG_STATUS beam and vblank move, TMU0's counter counts down; off, both read 0
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools'))


def main():
    import sh4sim
    bad = []
    m = sh4sim.Memory()
    m.write(0xFFA00040, 4, 0x8201)
    if m.read(0xFFA00040, 4) != 0x8201:
        bad.append('latch: read back %r, want 8201' % m.read(0xFFA00040, 4))
    m.device_reads[sh4sim.Memory.phys(0xFFA00040)] = [0x1234]
    if m.read(0xFFA00040, 4) != 0x1234 or m.read(0xFFA00040, 4) != 0x8201:
        bad.append('script: a scripted value comes first, then the latched one')
    if m.read(0xFFA00050, 4) != 0:
        bad.append('fresh: a register never written reads %r, want 0' % m.read(0xFFA00050, 4))
    h = sh4sim.Memory()
    h.hw_model = True
    spg = [h.read(0xA05F810C, 4) for _ in range(16 * 525)]
    if not any(v & 0x2000 for v in spg) or not any(not v & 0x2000 for v in spg) or h.read(0xFFD8000C, 4) == h.read(0xFFD8000C, 4):
        bad.append('hw_model: SPG_STATUS must show the vertical blank on some reads and not others, and TMU0\'s counter must move')
    if sh4sim.Memory().read(0xA05F810C, 4) != 0:
        bad.append('hw_model: off by default, SPG_STATUS reads 0')
    if bad:
        sys.exit('[ERROR] devlatch check failed:\n' + '\n'.join(bad))
    print('[devlatch] ok: a device register reads back its last write; a scripted read still comes first; unwritten reads 0')


if __name__ == '__main__':
    main()
