#!/usr/bin/env python3
"""Three more shapes with no C form (scripts/tools/5-generated/classify.py no_c_form). No game data, no compiler. Stdlib only.

Zombie Revenge, the last five functions the generator could not write:
  FUN_0c1efa5c, FUN_0c1efa78   4 bytes, `bra X` and the word 0x0c01: one 32-bit address of a pointer table, listed as a function
  FUN_0c0edea0, FUN_0c0edfc0   read fr12-fr15 after the first branch and never write them: values the caller left
  FUN_0c0e35b6                 loads the stack pointer from memory (a context restore)

    check.py      synthetic code:
                    data      one address word (its high half is no instruction) is data; `rts` / `nop` is not
                    frin      fr12 read after a branch and never written has no C form (also after fschg); written first, it has
                    sp        `mov.l @r5,r15` has no C form; a pop and `mov r14,r15` have
"""
import os
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
sys.path[:0] = [os.path.join(TOOLS, '5-generated'), TOOLS]
import toolpath  # noqa: E402,F401
import classify  # noqa: E402

BASE = 0x0C010000


def words(ws):
    return b''.join(struct.pack('<H', w) for w in ws)


def named(code):
    return classify.no_c_form(code, BASE, BASE, len(code))


def main():
    os.chdir(tempfile.mkdtemp())                     # no_c_form reads functions.txt
    open('functions.txt', 'w').write('F %08x 4 f\n' % BASE)
    bad = []
    addr = words([0x0008, 0x0C01]) + words([0x0009] * 6)       # the word 0x0C010008 (inside the code), then padding
    got = classify.no_c_form(addr, BASE, BASE, 4)
    if not any('data' in r for r in got):
        bad.append('data: one address word, its high half no instruction, is not named data: %s' % got)
    if any('data' in r for r in classify.no_c_form(words([0x000B, 0x0009]) + words([0x0009] * 6), BASE, BASE, 4)):
        bad.append('data: rts / nop is named data')
    read = [0x2448, 0x8900, 0x0009, 0xF8C2, 0x000B, 0x0009]    # tst r4,r4 / bt L / nop / L: fmul fr12,fr8 / rts / nop
    if not named(words(read)):
        bad.append('frin: fr12 read after a branch and never written is not named')
    if named(words([0xFC8D] + read)):                           # fldi0 fr12 first
        bad.append('frin: fr12 written first is named: %s' % named(words([0xFC8D] + read)))
    pair = [0xF3FD] + read                                      # fschg first: fmul does not depend on the size mode
    if not named(words(pair)):
        bad.append('frin: fr12 read by fmul in pair mode and never written is not named')
    if named(words([0xF3FD, 0xFC0C] + read)):                   # fmov fr0,fr12 in pair mode: a move of the pair, unknown
        bad.append('frin: a pair-mode move of fr12 is taken for a plain read: %s' % named(words([0xF3FD, 0xFC0C] + read)))
    vec = [0xF4ED] + read                                       # ftrv xmtrx,fv4 first: a vector that is not fr12-fr15
    if not named(words(vec)):
        bad.append('frin: an ftrv on fv4 hides the read of fr12')
    if named(words([0xFCED] + read)):                           # ftrv xmtrx,fv12 first: writes fr12-fr15
        bad.append('frin: an ftrv on fv12 is taken for a read: %s' % named(words([0xFCED] + read)))
    if not named(words([0x6F52, 0x000B, 0x0009])):
        bad.append('sp: mov.l @r5,r15 is not named')
    for ws, what in (([0x6EF6, 0x000B, 0x0009], 'a pop of r14'), ([0x6FE3, 0x000B, 0x0009], 'mov r14,r15')):
        if any('stack pointer' in r for r in named(words(ws))):
            bad.append('sp: %s is named a stack pointer load' % what)
    if bad:
        sys.exit('[ERROR] noformrules check failed:\n' + '\n'.join(bad))
    print('[noformrules] ok: a single address word, fr12-fr15 inputs after a branch and a stack pointer loaded from memory have no C form')


if __name__ == '__main__':
    main()
