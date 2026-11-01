#!/usr/bin/env python3
"""The tools that find functions the analysis missed (scripts/tools/1-2-baseline/missed_funcs.py, scripts/tools/boundaries.py) must not
list a table of words as a function. No game data, no compiler. Stdlib only.

Crazy Taxi FUN_0c089f4c: 52 bytes of a table (pointer words and small numbers) whose first words happen to decode as instructions
(bt, mul.l, add, a braf among the numbers). boundaries.py found a return-less walk that ended and accepted it, and it was added to
functions.txt as a function and sent to the draw, where it could not pass. A genuine function in the same gap must still be found.

    check.py      a temp repo: f1, then a gap holding a real function g (push pr ... rts, not listed) and a table t, then f2:
                    missed_funcs  g is a candidate; t is not
                    boundaries    g is "function"; t is not
                  and two more shapes, to keep the rule honest:
                    loop          a function whose bf goes back to an instruction of its own: accepted
                    tail          a bf that goes above the start of the piece: not a function (it belongs to the function before it)
                  and the three wrong Virtua Tennis entries of 2026-10-31, none a function:
                    pop           pops pr it never pushed (8c0b5cca: inside a fileLoad wrapper that starts with the push)
                    read          reads r2 before writing it (8c0d2b02: the mov.l that sets r2 is the instruction before)
                    data          a pointer word, 0x8c087ff4, whose low half decodes as add #-12,r15 (8c0886cc)
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
BASE = 0x8C010000
W = lambda *h: struct.pack('<%dH' % len(h), *h)

F1 = W(0x4F22, 0x4F26, 0x000B, 0x0009)                                         # 0: sts.l pr / lds.l pr / rts / nop           (8 bytes)
G = W(0x4F22, 0x7FFC, 0x7F04, 0x4F26, 0x000B, 0x0009)                          # 8: a function the analysis missed             (12 bytes)
T = (W(0x89C0, 0x0C17, 0x7BA8) + W(0x8C40, 0x0C2B) * 3 +                       # 20: bt / mul.l / add: decodes; three pointer words
     W(0x0046, 0x0000, 0x0041, 0x0000, 0x003C, 0x0000, 0x0023, 0x0000, 0x0000))  # small numbers, a braf r0 among them          (36 bytes)
L = W(0xE400, 0x7401, 0x8BFD, 0x000B, 0x0009)                                  # 56: a loop that branches back inside itself:
#                                                                                  mov #0,r4 / add #1,r4 / bf -6 (to the add) / rts / nop (10 bytes)
TAIL = W(0x8BF0, 0x000B, 0x0009)                                               # 66: bf to far above its own start: a tail of an earlier function
POP = W(0x6013, 0x4F26, 0x000B, 0x0009)                                        # 72: mov r1,r0 / lds.l @r15+,pr / rts / nop: pops a pr it never pushed
READ = W(0x6322, 0x2338, 0x000B, 0x0009)                                       # 80: mov.l @r2,r3 / tst r3,r3 / rts / nop: reads r2 before writing it
DATA = W(0x7FF4, 0x8C08, 0x000B, 0x0009)                                       # 88: 0x8c087ff4, a pointer word: add #-12,r15 then no instruction
F2 = W(0x000B, 0x0009)                                                         # 96: rts / nop
CODE = F1 + G + T + L + TAIL + POP + READ + DATA + F2
G_AT, T_AT = BASE + len(F1), BASE + len(F1) + len(G)
L_AT = T_AT + len(T)
TAIL_AT = L_AT + len(L)
POP_AT = TAIL_AT + len(TAIL)
READ_AT = POP_AT + len(POP)
DATA_AT = READ_AT + len(READ)
FUNCS = 'F %08x 8 f1\nF %08x 4 f2\n' % (BASE, DATA_AT + len(DATA))


def run(tmp, *args):
    r = subprocess.run([sys.executable] + list(args), cwd=tmp, capture_output=True, text=True)
    return r.stdout + r.stderr


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(CODE)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write(FUNCS)
        open(os.path.join(tmp, 'cands.txt'), 'w').write('%08x\n%08x\n%08x\n%08x\n%08x\n%08x\n%08x\n' % (G_AT, T_AT, L_AT, TAIL_AT, POP_AT, READ_AT, DATA_AT))

        out = run(tmp, 'tools/1-2-baseline/missed_funcs.py', '1ST_READ.BIN', '%08X' % BASE, 'functions.txt')
        listed = {l.split()[0] for l in out.splitlines() if l[:8].strip() and all(c in '0123456789abcdef' for c in l[:8])}
        if '%08x' % G_AT not in listed:
            bad.append('missed_funcs: the real function at %08x is not a candidate (%r)' % (G_AT, out.strip()[-200:]))
        if '%08x' % T_AT in listed:
            bad.append('missed_funcs: the table at %08x is a candidate: words that happen to decode are not code' % T_AT)

        out = run(tmp, 'tools/boundaries.py', 'cands.txt')
        rows = {}
        for l in out.splitlines():
            p = l.split()
            if p and len(p[0]) == 8 and len(p) > 1:
                rows[int(p[0], 16) | 0x80000000 if int(p[0], 16) < 0x80000000 else int(p[0], 16)] = p[1]
        # boundaries.py prints the 0C mirror; compare by the low 29 bits
        by = {k & 0x1FFFFFFF: v for k, v in rows.items()}
        if by.get(G_AT & 0x1FFFFFFF) != 'function':
            bad.append('boundaries: the real function at %08x is %r, want function (%r)' % (G_AT, by.get(G_AT & 0x1FFFFFFF), out.strip()[-200:]))
        if by.get(T_AT & 0x1FFFFFFF) == 'function':
            bad.append('boundaries: the table at %08x is accepted as a function' % T_AT)
        if by.get(L_AT & 0x1FFFFFFF) != 'function':
            bad.append('boundaries: a function whose loop branches back inside itself, at %08x, is %r (%r)' % (L_AT, by.get(L_AT & 0x1FFFFFFF), out.strip()[-200:]))
        if by.get(TAIL_AT & 0x1FFFFFFF) == 'function':
            bad.append('boundaries: the piece at %08x, whose conditional branch leaves it backwards, is accepted as a function' % TAIL_AT)
        for at, what in ((POP_AT, 'pops a pr it never pushed'), (READ_AT, 'reads r2 before writing it'), (DATA_AT, 'has no instruction after its first')):
            if by.get(at & 0x1FFFFFFF) == 'function':
                bad.append('boundaries: the piece at %08x, which %s, is accepted as a function (%r)' % (at, what, out.strip()[-300:]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for b in bad:
        print('FAIL', b)
    print('findfuncs: %s' % ('OK' if not bad else '%d failures' % len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
