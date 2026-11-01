#!/usr/bin/env python3
"""Which words the shifted layout moves (scripts/tools/8-build/shift.py word()). No game data, no compiler. Stdlib only.

Crazy Taxi's first shifted build (2026-10-31: everything from 0C0739C0 up 0x10000) booted to a black-and-white SEGA logo and froze
at the start menu: 477 words that point into the moved range kept their old value, for two reasons.

    check.py      a temp repo: a function listed shorter than its code, a table of pointers, and a byte table:
                    pool     a literal pool word the function loads from past its listed size, sitting inside the next function's
                             listed bytes, is moved (it was read as two instructions: Crazy Taxi nlSysSetDirectListTypeLatency2V,
                             getSystemMetrics, 178 such words in the NAOMI library)
                    table    a table of pointers whose every byte is under 0x40 (0C01xxxx: low addresses) is moved (it was taken for
                             a byte table: Crazy Taxi's data at 0C09xxxx, 272 words)
                    bytes    a run of small bytes that only looks like an address (07070808 | 0b0b0c0c: Virtua Tennis) stays
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
BASE = 0x0C010000
W = lambda *h: struct.pack('<%dH' % len(h), *h)
L = lambda *v: struct.pack('<%dI' % len(v), *v)

CODE = (W(0xA002, 0x0009, 0x0009, 0x0009) +          # 00 f1: bra 08 / nop / pad: listed as 4 bytes
        W(0xD101, 0x000B) +                            # 08 mov.l @(16),r1 (past f1's listed size) / rts
        W(0x0009, 0x0009) +                            # 0C f2 starts: nop / nop
        L(0x0C010120) +                                # 10 the pool word f1 loads, inside f2's listed bytes
        W(0x000B, 0x0009))                             # 14 rts / nop
DATA = (L(0x0C010120, 0x0C010124, 0x0C010128) +       # 18 a table of pointers, every byte under 0x40
        L(0x08080707, 0x0C0C0B0B))                     # 24 a byte table: the second word looks like an address
IMAGE = CODE + DATA + b'\0' * (0x200 - len(CODE + DATA))


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(IMAGE)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x 4 f1\nF %08x 12 f2\n' % (BASE, BASE + 0x0C))
        open(os.path.join(tmp, 'layout.txt'), 'w').write('game 0C010000 0C010200\nkeep 0C010018 0C010200\nshift 00010000 0C100000\n')
        script = ("import sys, struct; sys.path.insert(0, 'tools'); sys.path.insert(0, 'tools/8-build'); import toolpath, shift\n"
                  "img = open('1ST_READ.BIN', 'rb').read()\n"
                  "for at in (0x10, 0x18, 0x1C, 0x20, 0x28):\n"
                  "    v = struct.unpack_from('<I', img, at)[0]\n"
                  "    r = shift.word(v, 0x0C010000 + at)\n"
                  "    print('%x %s' % (at, 'None' if r is None else '%08x' % r))\n")
        r = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        got = dict(l.split() for l in r.stdout.split('\n') if l.strip() and len(l.split()) == 2)
        if got.get('10') != '0c020120':
            bad.append('pool: the word f1 loads past its listed size is %r, want 0c020120\n%s' % (got.get('10'), r.stdout[-400:]))
        for at, want in (('18', '0c020120'), ('1c', '0c020124'), ('20', '0c020128')):
            if got.get(at) != want:
                bad.append('table: the pointer at +%s is %r, want %s' % (at, got.get(at), want))
        if got.get('28') != 'None':
            bad.append('bytes: 0c0c0b0b in a byte table was moved: %r' % got.get('28'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] shiftrefs check failed:\n' + '\n'.join(bad))
    print('[shiftrefs] ok: pool words past a listed size and tables of low pointers move; a byte table stays')


if __name__ == '__main__':
    main()
