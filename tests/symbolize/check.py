#!/usr/bin/env python3
"""The split's address words written as names (scripts/tools/1-2-baseline/symbolize.py). No game data, no compiler. Stdlib only.

A movable build needs every address as a name the linker fills in. pointers.py decides which words are addresses; symbolize.py
rewrites them in the split's raw words, where they sit, as the piece that holds the target plus the distance into it.

    check.py      a temp repo split by split_asm.py: a function whose pool word points into a data piece, a piece that starts
                  2 bytes past a 4-byte boundary with an address in it, a pointer past the end of the image and one in the 8C mirror:
                    name      the pool word is .DATA.L _data_20+H'4, and _data_20 is imported
                    aligned2  the word in the piece that starts at +0E is written at its own place (no padding asked for)
                    bss       an address past the image is _bss+offset, and bss.src reserves the range up to the fixed line
                    mirror    an 8C-topped word in a game linked at 0C keeps its mirror: +H'80000000
                    numbers   a word that is no address is the same .DATA.W pair as before
                    branch    a bsr from f1 into data_20 is BSR _data_20+H'4 (the linker relocates it)
                    data      data_20 is listed as a function; its word shaped like a bra no code reaches stays a word (Crazy Taxi
                              meshVertexIndexBlock: such words written as branches did not assemble, and would change once moved)
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

IMAGE = (W(0xD101, 0xB00F, 0x0009, 0x000B) +       # 00 f1: mov.l @(8),r1 / bsr 24 (data_20 + 4) / nop / rts
         L(0x0C010024) +                            # 08 its pool word: data_20 + 4
         W(0x0009) +                                # 0C
         W(0x0009) +                                # 0E data_0e starts here (2 past a boundary)
         L(0x0C010000) +                            # 10 an address in data_0e: f1
         L(0x0C010300) +                            # 14 past the image (it is 0x40 bytes): the BSS
         L(0x8C010008) +                            # 18 the 8C mirror of f1's pool
         L(0x12345678) +                            # 1C a number
         L(0x00000001, 0x0000AFF0) +                # 20 data_20, listed as a function: +24 is shaped like bra 08 (into f1)
         L(0, 0, 0, 0, 0, 0))                       # 28..40: the image ends at +40


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(IMAGE)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'layout.txt'), 'w').write('game 0C010000 0C010040\nfixed 0C010400\n')
        fl = 'F %08x 12 f1\nD %08x 0 data_0e\nF %08x 8 data_20\n' % (BASE, BASE + 0x0E, BASE + 0x20)
        open(os.path.join(tmp, 'report.txt'), 'w').write(fl)
        run = lambda *a: subprocess.run([sys.executable] + list(a), cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        universal_newlines=True).stdout
        out = run('tools/1-2-baseline/split_asm.py', '1ST_READ.BIN', '%08X' % BASE, 'report.txt', '.')
        out += run('tools/1-2-baseline/pointers.py')
        out += run('tools/1-2-baseline/symbolize.py', 'sym')
        get = lambda f: open(os.path.join(tmp, 'sym', 'asm', f)).read() if os.path.exists(os.path.join(tmp, 'sym', 'asm', f)) else ''
        f1, d0e = get('0c010000_f1.src'), get('0c01000e_data_0e.src')
        if ".DATA.L     _data_20+H'4" not in f1 or '.IMPORT     _data_20' not in f1:
            bad.append('name: f1\'s pool word is not _data_20+H\'4 (imported):\n' + f1)
        if "BSR         _data_20+H'4" not in f1:
            bad.append('branch: f1\'s bsr into data_20 is not BSR _data_20+H\'4:\n' + f1)
        d20 = get('0c010020_data_20.src')
        if 'BRA' in d20 or ".DATA.W     H'AFF0" not in d20:
            bad.append('data: a branch-shaped word no code reaches (data listed as a function) was written as a branch:\n' + d20)
        lines = [l.strip() for l in d0e.split('\n') if l.strip().startswith('.DATA')]
        if lines[:2] != ['.DATA.W     H\'0009', '.DATA.L     _f1']:
            bad.append('aligned2: data_0e does not start .DATA.W H\'0009, .DATA.L _f1:\n' + d0e)
        if ".DATA.L     _bss+H'2C0" not in d0e:
            bad.append('bss: the word past the image is not _bss+H\'2C0:\n' + d0e)
        if ".DATA.L     _f1+H'8+H'80000000" not in d0e:
            bad.append('mirror: the 8C word is not _f1+H\'8+H\'80000000:\n' + d0e)
        if ".DATA.W     H'5678" not in d0e or ".DATA.W     H'1234" not in d0e:
            bad.append('numbers: 0x12345678 is not the same .DATA.W pair:\n' + d0e)
        bss = open(os.path.join(tmp, 'sym', 'bss.src')).read() if os.path.exists(os.path.join(tmp, 'sym', 'bss.src')) else ''
        if ".RES.B      H'3C0" not in bss:
            bad.append('bss: bss.src does not reserve 0C010040-0C010400 (H\'3C0):\n' + bss)
        if bad:
            bad.append(out[-800:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] symbolize check failed:\n' + '\n'.join(bad))
    print('[symbolize] ok: address words are names where they sit (pool, 2-aligned piece, BSS, other mirror); numbers stay')


if __name__ == '__main__':
    main()
