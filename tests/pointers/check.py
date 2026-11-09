#!/usr/bin/env python3
"""Which words are addresses (scripts/tools/1-2-baseline/pointers.py): one word per rule. No game data, no compiler. Stdlib only.

A movable build writes every address as a name, so each word is classified once, from the bytes, and the decision is written
down (build/pointers.txt). Crazy Taxi's and Virtua Tennis's shifted builds found the rules one crash at a time: pool words past
a listed size, tables of low pointers, byte tables that look like addresses.

    check.py      a temp repo: a function, its pool, a table of pointers, a byte table, a word into a fixed buffer, two
                  instructions that read as an address, and a words.txt override:
                    pool      the word a mov.l @(disp,pc) reads is P pool
                    code      a 0C-topped pair of instructions inside the function is not a candidate
                    table     pointers whose bytes are all under 0x40 (0C01xxxx) are P 0c
                    bytes     a byte table that only looks like an address (07070808 | 0b0b0c0c) is N bytes
                    fixed     an address at or above layout.txt's fixed line is N fixed
                    8c        an 8C-topped word in data is P 8c
                    codefn    a word inside a function whose value is a listed function's start is P codefn
                    coderun   three words at a stride of 8 with close values inside a function are P coderun; two are not
                    words     words.txt N on a word the rules take as an address makes it N words
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

CODE = (W(0xD102, 0x000B) +                            # 00 mov.l @(8),r1 (reads 0C) / rts
        W(0x0009) + W(0xE10C, 0x0009) +                # 04 nop / 06 mov #12,r1 + nop: the pair 0C 0009 ... (see 08)
        W(0x0009) +                                    # 0A pad
        L(0x0C010040))                                 # 0C the pool word
CODE = CODE[:8] + W(0x0010, 0x0C01) + CODE[12:]        # 08 two instructions that read as 0C010010
DATA = (L(0x0C010120, 0x0C010124, 0x0C010128) +       # 10 a table of pointers, every byte under 0x40
        L(0x08080707, 0x0C0C0B0B) +                    # 1C a byte table: the second word looks like an address
        L(0x0C600000) +                                # 24 a fixed buffer
        L(0x8C010000) +                                # 28 8C on top
        L(0x0C010130))                                 # 2C taken as an address by the rules, a number by words.txt
F2 = (L(0x0C010000) + W(0x0009, 0x0009) +             # 40 a function pointer to f1's start, then nops
      L(0x0C010100, 0) + L(0x0C010108, 0) + L(0x0C010110) +   # 48, 50, 58 a table of three at a stride of 8
      W(0x0009, 0x0009) + L(0x0C010400, 0) + L(0x0C010800)) # 5C pad, 60 and 68 two far words that are no run
IMAGE = CODE + DATA + b'\0' * (0x40 - len(CODE + DATA)) + F2 + b'\0' * (0x200 - 0x40 - len(F2))


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(IMAGE)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x 12 f1\nD %08x 0 data_10\nF %08x 56 f2\n' % (BASE, BASE + 0x10, BASE + 0x40))
        open(os.path.join(tmp, 'layout.txt'), 'w').write('game 0C010000 0C010200\nfixed 0C500000\n')
        open(os.path.join(tmp, 'words.txt'), 'w').write('N 0C01002C   # a test override\n')
        r = subprocess.run([sys.executable, 'tools/1-2-baseline/pointers.py'], cwd=tmp, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, universal_newlines=True)
        rows = {}
        if os.path.exists(os.path.join(tmp, 'build', 'pointers.txt')):
            for l in open(os.path.join(tmp, 'build', 'pointers.txt')):
                p = l.split()
                rows[int(p[0], 16) - BASE] = (p[2], p[3])
        want = {0x0C: ('P', 'pool'), 0x10: ('P', '0c'), 0x14: ('P', '0c'), 0x18: ('P', '0c'), 0x20: ('N', 'bytes'),
                0x24: ('N', 'fixed'), 0x28: ('P', '8c'), 0x2C: ('N', 'words'),
                0x40: ('P', 'codefn'), 0x48: ('P', 'coderun'), 0x50: ('P', 'coderun'), 0x58: ('P', 'coderun')}
        for at, w in sorted(want.items()):
            if rows.get(at) != w:
                bad.append('+%02X: %r, want %r' % (at, rows.get(at), w))
        if 0x08 in rows:
            bad.append('code: the instruction pair at +08 is a candidate: %r' % (rows[0x08],))
        for at in (0x60, 0x68):
            if at in rows:
                bad.append('coderun: +%02X is a far word beside a run, not part of it: %r' % (at, rows[at]))
        if bad:
            bad.append(r.stdout[-600:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] pointers check failed:\n' + '\n'.join(bad))
    print('[pointers] ok: pool words, tables of low pointers and 8C words are addresses; byte tables, fixed buffers and '
          'words.txt numbers are not; instructions are not candidates')


if __name__ == '__main__':
    main()
