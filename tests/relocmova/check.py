#!/usr/bin/env python3
"""A function with no C is re-assembled from its original code (scripts/tools/8-build/relocasm.py piece). A `mova` that names a word in
another function's pool is accepted when the word is read once through r0 (`fmov.s @r0,fr` / `mov.l @r0,r`), the piece then keeps a copy
of the word. The check looked only at the next four instructions, so a mova whose load came later was refused with "names data outside
the function" although nothing else touched r0 (Virtua Tennis nlObjPutInit: `mova ...,r0`, eleven instructions of setup, then
`fmov.s @r0,fr10`; the build stopped there). The load is now looked for through the straight-line code that does not touch r0.
No game data, no compiler. Stdlib only.

    check.py      a temp repo, function f at 0C020000 (0x20 bytes) and g after it, the float 1.0 in the gap after g (another function's pool):
                    far        mova, six instructions that leave r0 alone, fmov.s @r0,fr8: accepted, with a local copy of the word
                    touched    mova, then an instruction that writes r0, then the load: refused (the load reads something else)
                    branch     mova, a branch before any use of r0: refused
                    delay      the load in the delay slot of a jsr is the load: accepted; a slot that is no load: refused
"""
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')


def image(code):
    b = bytearray(b'\x09\x00' * 0x80)
    for i, w in enumerate(code):
        b[2 * i:2 * i + 2] = struct.pack('<H', w)
    b[0x5C:0x60] = struct.pack('<I', 0x3F800000)
    b[0x40:0x44] = struct.pack('<HH', 0x000B, 0x0009)
    return bytes(b)


def run(code):
    import boundaries
    import relocasm
    boundaries.BIN = image(code)
    F = [(0x0C020000, 0x20, 'f'), (0x0C020040, 4, 'g')]
    return relocasm.piece(0, F, {a: n for a, s, n in F})


def main():
    tmp = tempfile.mkdtemp()
    try:
        os.chdir(tmp)
        open('layout.txt', 'w').write('game 0C020000 0C020100\n')
        open('BASE', 'w').write('0C020000\n')
        open('functions.txt', 'w').write('F 0c020000 32 f\nF 0c020040 4 g\n')
        open('1ST_READ.BIN', 'wb').write(image([]))
        sys.path.insert(0, os.path.join(TOOLS, '8-build'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        bad = []
        mova = 0xC716                       # mova @(22*4+4,pc),r0: 0x0C02005C, past g's entry
        fill = [0x6213] * 6                 # mov r1,r2
        load = 0xF808                       # fmov.s @r0,fr8
        end = [0x000B, 0x0009]
        text, err = run([mova] + fill + [load] + end)
        if text is None:
            bad.append('far: refused: %s' % err)
        elif 'MOVA' not in text:
            bad.append('far: no MOVA in the piece')
        text, err = run([mova, 0xE001] + fill + [load] + end)          # mov #1,r0 before the load
        if text is not None:
            bad.append('touched: accepted although r0 is overwritten before the load')
        text, err = run([mova, 0x8901, 0x0009] + fill + [load] + end)     # bt +1 before any use
        if text is not None:
            bad.append('branch: accepted although a branch comes before the load')
        # delay: the load in the delay slot of a call (sysVideoSelect, Virtua Tennis: `mova ...,r0 / jsr @r3 / fmov.s @r0,fr4`) is the load
        text, err = run([mova, 0x430B, load] + end)                      # mova / jsr @r3 / fmov.s @r0,fr8
        if text is None:
            bad.append('delay: a load in the delay slot of a jsr was refused: %s' % err)
        text, err = run([mova, 0x430B, 0xE001] + end)                    # mova / jsr @r3 / mov #1,r0: the slot overwrites r0, no load
        if text is not None:
            bad.append('delay: accepted although the delay slot does not load through r0')
        if not bad:
            print('[relocmova] ok: a mova whose load comes later through code that leaves r0 alone is accepted; an overwritten r0 or a branch refuses it')
            return
        sys.exit('[ERROR] relocmova check failed:\n' + '\n'.join(bad))
    finally:
        os.chdir('/')
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
