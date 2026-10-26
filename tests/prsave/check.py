#!/usr/bin/env python3
"""The stack words a call is compared on (scripts/tools/sh4sim.py stackchg) on a synthetic function, no game data. Stdlib only.

    check.py      sts.l pr,@-r15 then a call: the word the prologue saved pr into sits at SP at the call, where a fifth argument would be.
                    prsave    it is not counted as written for the call: a saved return address is never an argument (Virtua Tennis
                              cpuDblThink: its call to cpuDblHitCheck was compared on that word, the simulator's return-address sentinel
                              in the original against 0 in the C)
                    pushed    a word pushed for the call (mov.l r1,@-r15) still is
"""
import os
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401
import sh4sim  # noqa: E402

BASE = 0x8C010000


def run(words, pool):
    code = b''.join(struct.pack('<H', w) for w in words)
    code += b'\x09\x00' * ((-len(code)) % 4) + struct.pack('<I', pool)
    code += struct.pack('<HH', 0x000B, 0x0009)               # the callee: rts / nop
    d = tempfile.mkdtemp()
    open(os.path.join(d, 'exe.bin'), 'wb').write(code)
    return sh4sim.run({'about': 'prsave', 'poke': {}, 'exe': 'exe.bin', 'base': '%08X' % BASE, 'entry': '%08X' % BASE,
                       'end': '%08X' % (BASE + len(code))}, d)


def main():
    bad = []
    # sts.l pr,@-r15 / mov.l @(pool),r1 / jsr @r1 / nop / lds.l @r15+,pr / rts / nop ; pool at +16 -> the callee at +20
    r = run([0x4F22, 0xD103, 0x410B, 0x0009, 0x4F26, 0x000B, 0x0009, 0x0009], BASE + 20)
    ch = r['calls'][0].get('stackchg') if r.get('calls') else None
    if r['error'] or ch is None or ch[0]:
        bad.append('prsave: the word pr was saved into counts as written for the call: %s / %s' % (ch, r['error']))
    # the same with a word pushed for the call after the save: sts.l pr / mov #7,r1 / mov.l r1,@-r15 / mov.l @(pool),r1 / jsr / nop /
    # add #4,r15 / lds.l / rts / nop ; pool at +20 -> the callee at +24
    r = run([0x4F22, 0xE107, 0x2F16, 0xD103, 0x410B, 0x0009, 0x7F04, 0x4F26, 0x000B, 0x0009], BASE + 24)
    ch = r['calls'][0].get('stackchg') if r.get('calls') else None
    if r['error'] or ch is None or not ch[0]:
        bad.append('pushed: a word pushed for the call is not counted as written: %s / %s' % (ch, r['error']))
    if bad:
        sys.exit('[ERROR] prsave check failed:\n' + '\n'.join(bad))
    print('[prsave] ok: the word the prologue saved pr into is not an argument; a word pushed for the call is')


if __name__ == '__main__':
    main()
