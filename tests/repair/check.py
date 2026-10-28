#!/usr/bin/env python3
"""Pointer repair of a drawn case (scripts/tools/5-generated/gen_equiv/directed.py repair), with the real simulator on synthetic code. No
game data, no compiler. Stdlib only.

Zombie Revenge FUN_0c05265c (and the other small functions whose drawing timed out) loops over a table a global describes: {array, count}.
With the drawn memory zero, dt wraps the count to 2^32 and every case runs to the step cap; with a count, the array pointer is 0 and each
entry's pointer too. repair runs the case, and while it fails it finds where the value went wrong came from (directed.provenance) and
sets that source (directed.apply): a dt counter to 2, a pointer that read or wrote outside RAM to a fresh zeroed block.

    check.py      G = {array, count} at BASE+0x100, zeros; the function: r5 = &G, r4 = G.array, r5 = G.count; loop: r3 = *r4;
                  *r3 = 1; dt r5; r4 += 4:
                    plain     with no repair the case does not finish (the step cap)
                    repaired  repair gives a case the original finishes on, with no access outside RAM, in at most 8 rounds
                  hang: r6 = &H; r4 = *r6; tst #8 against r4; bt to a branch to itself (Zombie Revenge FUN_0c0cac3a stops there on a
                  record whose flag bit is clear):
                    plain     the zero case spins to the step cap
                    repaired  repair sets the tested word so the test goes the other way, and the case finishes
                  index: r0 = &T; shll2 r4; *(r0 + r4) = r1, r4 drawn as a pointer (Virtua Tennis nlSetPaletteData: an index into
                  gPaletteData):
                    repaired  repair traces the address back through the shift and sets the index to 0: no access outside RAM
                  addindex: r4 = &T; shll2 r5; add r5,r4; *r4 = r1 (emotFaceReset: a table entry plus a call's answer times 4):
                    repaired  the index is found through the register add and set to 0
                  callindex: the same with the index a call's answer, the range given as 0C... while the code runs at 8C... (gen_drv.mend
                  passes 0C..., Virtua Tennis runs at 8C...: no call answer was ever found there):
                    repaired  the call's answer is set to 0
"""
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
sys.path[:0] = [os.path.join(TOOLS, '5-generated', 'gen_equiv'), os.path.join(TOOLS, '5-generated'), TOOLS]
import toolpath  # noqa: E402,F401
import sh4sim  # noqa: E402
import directed  # noqa: E402

BASE = 0x8C010000


def main():
    code = [0xD505,              # mov.l @(pool),r5   ; = &G
            0x6452,              # mov.l @r5,r4       ; array
            0x5551,              # mov.l @(4,r5),r5   ; count
            0x6342,              # loop: mov.l @r4,r3
            0xE001,              # mov #1,r0
            0x2302,              # mov.l r0,@r3
            0x4510,              # dt r5
            0x8FFA,              # bf/s loop
            0x7404,              # add #4,r4
            0x000B, 0x0009]      # rts / nop
    body = b''.join(struct.pack('<H', w) for w in code)
    pool_at = 0x18
    body += b'\x09\x00' * ((pool_at - len(body)) // 2) + struct.pack('<I', BASE + 0x100)
    exe = body + b'\x00' * (0x200 - len(body))
    d = tempfile.mkdtemp()
    bad = []
    try:
        open(os.path.join(d, 'exe.bin'), 'wb').write(exe)
        def run(case, trace=True):
            return sh4sim.run(dict(case, exe='exe.bin', base='%08X' % BASE, entry='%08X' % BASE, end='%08X' % (BASE + 0x16), steps=20000,
                                   trace=trace), d)
        r = run({})
        if not r['error']:
            bad.append('plain: the zero case finished (%s steps): the test does not show the wrap' % r['steps'])
        try:
            fixed = directed.repair({}, run, (0x0C000000 | (BASE & 0x1FFFFFFF), 0x0C000000 | ((BASE + 0x16) & 0x1FFFFFFF)), hw=False)
        except AttributeError:
            sys.exit('[ERROR] repair check failed:\nrepaired: directed.py has no repair()')
        r2 = run(fixed or {})
        if not fixed or r2['error'] or r2.get('devices'):
            bad.append('repaired: no case the original finishes on cleanly: %s / %s / devices %s' % (fixed, r2['error'], (r2.get('devices') or [])[:2]))
        hang = [0xD604,              # mov.l @(pool),r6   ; = &H
                0x6462,              # mov.l @r6,r4
                0xE708,              # mov #8,r7
                0x2478,              # tst r7,r4
                0x8901,              # bt hang
                0x000B, 0x0009,      # rts / nop
                0xAFFE, 0x0009]      # hang: bra hang / nop
        body = b''.join(struct.pack('<H', w) for w in hang) + b'\x09\x00' + struct.pack('<I', BASE + 0x100)
        open(os.path.join(d, 'hang.bin'), 'wb').write(body + b'\x00' * (0x200 - len(body)))
        def run2(case, trace=True):
            return sh4sim.run(dict(case, exe='hang.bin', base='%08X' % BASE, entry='%08X' % BASE, end='%08X' % (BASE + 0x12), steps=20000,
                                   trace=trace), d)
        if not run2({})['error']:
            bad.append('hang plain: the zero case finished: the test does not show the hang')
        fixed = directed.repair({}, run2, (0x0C000000 | (BASE & 0x1FFFFFFF), 0x0C000000 | ((BASE + 0x12) & 0x1FFFFFFF)), hw=False)
        r3 = run2(fixed or {})
        if not fixed or r3['error']:
            bad.append('hang repaired: no case the original finishes on: %s / %s' % (fixed, r3['error']))
        idx = [0xD002,               # mov.l @(pool),r0   ; = &T
               0x4408,               # shll2 r4
               0x0416,               # mov.l r1,@(r0,r4)
               0x000B, 0x0009,       # rts / nop
               0x0009]
        body = b''.join(struct.pack('<H', w) for w in idx) + struct.pack('<I', BASE + 0x100)
        open(os.path.join(d, 'idx.bin'), 'wb').write(body + b'\x00' * (0x200 - len(body)))
        def run3(case, trace=True):
            return sh4sim.run(dict(case, exe='idx.bin', base='%08X' % BASE, entry='%08X' % BASE, end='%08X' % (BASE + 0xA), steps=20000,
                                   trace=trace), d)
        drawn = {'regs': {'r4': '0C800000'}}
        if not run3(drawn).get('devices'):
            bad.append('index plain: the drawn index reached nothing outside RAM: the test does not show it')
        fixed = directed.repair(drawn, run3, (0x0C000000 | (BASE & 0x1FFFFFFF), 0x0C000000 | ((BASE + 0xA) & 0x1FFFFFFF)), hw=False)
        r4 = run3(fixed or drawn)
        if not fixed or r4['error'] or r4.get('devices'):
            bad.append('index repaired: %s / %s / devices %s' % (fixed, r4['error'], (r4.get('devices') or [])[:2]))
        add = [0xD402,               # mov.l @(pool),r4   ; = &T
               0x4508,               # shll2 r5
               0x345C,               # add r5,r4
               0x2412,               # mov.l r1,@r4
               0x000B, 0x0009]       # rts / nop
        body = b''.join(struct.pack('<H', w) for w in add) + struct.pack('<I', BASE + 0x100)
        open(os.path.join(d, 'add.bin'), 'wb').write(body + b'\x00' * (0x200 - len(body)))
        def run4(case, trace=True):
            return sh4sim.run(dict(case, exe='add.bin', base='%08X' % BASE, entry='%08X' % BASE, end='%08X' % (BASE + 0xC), steps=20000,
                                   trace=trace), d)
        drawn = {'regs': {'r5': '0C800000'}}
        if not run4(drawn).get('devices'):
            bad.append('addindex plain: the drawn index reached nothing outside RAM: the test does not show it')
        fixed = directed.repair(drawn, run4, (0x0C000000 | (BASE & 0x1FFFFFFF), 0x0C000000 | ((BASE + 0xC) & 0x1FFFFFFF)), hw=False)
        r5 = run4(fixed or drawn)
        if not fixed or r5['error'] or r5.get('devices'):
            bad.append('addindex repaired: %s / %s / devices %s' % (fixed, r5['error'], (r5.get('devices') or [])[:2]))
        cl = [0x4F22,                # sts.l pr,@-r15
              0xD405,                # mov.l @(pool),r4   ; = &T
              0xB006,                # bsr f (outside the function)
              0x0009,                # nop
              0x4008,                # shll2 r0
              0x340C,                # add r0,r4
              0x2412,                # mov.l r1,@r4
              0x4F26,                # lds.l @r15+,pr
              0x000B, 0x0009,        # rts / nop
              0x000B, 0x0009]        # f: rts / nop
        body = b''.join(struct.pack('<H', w) for w in cl) + struct.pack('<I', BASE + 0x100)
        open(os.path.join(d, 'call.bin'), 'wb').write(body + b'\x00' * (0x200 - len(body)))
        def run5(case, trace=True):
            return sh4sim.run(dict(case, exe='call.bin', base='%08X' % BASE, entry='%08X' % BASE, end='%08X' % (BASE + 0x14), steps=20000,
                                   trace=trace), d)
        drawn = {'calls': [{'r0': '0C930100'}] * 3}
        if not run5(drawn).get('devices'):
            bad.append('callindex plain: the drawn answer reached nothing outside RAM: the test does not show it')
        fixed = directed.repair(drawn, run5, (0x0C000000 | (BASE & 0x1FFFFFFF), 0x0C000000 | ((BASE + 0x14) & 0x1FFFFFFF)), hw=False)
        r6 = run5(fixed or drawn)
        if not fixed or r6['error'] or r6.get('devices'):
            bad.append('callindex repaired: %s / %s / devices %s' % (fixed, r6['error'], (r6.get('devices') or [])[:2]))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] repair check failed:\n' + '\n'.join(bad))
    print('[repair] ok: a case running into a wrapped count, null pointers or a deliberate hang is repaired at their sources')


if __name__ == '__main__':
    main()
