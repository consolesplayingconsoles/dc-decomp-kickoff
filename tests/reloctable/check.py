#!/usr/bin/env python3
"""An entry in functions.txt that is really a table of code pointers (a switch's jump table the analysis took for a function) is data.
relocasm.piece decided that only from the first word: a table whose first pointer's low half happens to decode as an instruction
(0x8C0F7FF0 starts with 7FF0, add #-16,r15) was read as code and the build stopped at the next word with "cannot decode"
(Virtua Tennis FUN_8c0f8220, the jump table of nlSetIntrFunction). An aligned entry whose first two words both point into the game code
is a pointer table. No game data, no compiler. Stdlib only.

    check.py      a temp repo, f at 0C020000 (16 bytes) holding pointers 0x8C027FF0 and 0x8C020040, then g:
                    table     f is accepted as data (a piece, no "cannot decode")
                    code      a real function whose first word is not a pointer pair still reads as code
"""
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')


def image(words):
    b = bytearray(b'\x09\x00' * 0x80)
    for i, w in enumerate(words):
        b[2 * i:2 * i + 2] = struct.pack('<H', w)
    return bytes(b)


def run(words):
    import boundaries
    import relocasm
    boundaries.BIN = image(words)
    F = [(0x0C020000, 0x10, 'f'), (0x0C020040, 4, 'g')]
    return relocasm.piece(0, F, {a: n for a, s, n in F})


def main():
    tmp = tempfile.mkdtemp()
    try:
        os.chdir(tmp)
        open('layout.txt', 'w').write('game 0C020000 0C030000\n')
        open('BASE', 'w').write('0C020000\n')
        open('functions.txt', 'w').write('F 0c020000 16 f\nF 0c020040 4 g\n')
        open('1ST_READ.BIN', 'wb').write(image([]))
        sys.path.insert(0, os.path.join(TOOLS, '8-build'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        bad = []
        lo, hi = 0x7FF0, 0x8C02
        text, err = run([lo, hi, 0x0040, 0x8C02, 0x0009, 0x0009, 0x0009, 0x0009])
        if text is None:
            bad.append('table: refused: %s' % err)
        text, err = run([0x7FF0, 0x000B, 0x0009, 0x0009])                 # add #-16,r15; rts; nop: code
        if text is None:
            bad.append('code: a real function was refused: %s' % err)
        if not bad:
            print('[reloctable] ok: an entry of two pointers into the game code is data, a real function still reads as code')
            return
        sys.exit('[ERROR] reloctable check failed:\n' + '\n'.join(bad))
    finally:
        os.chdir('/')
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
