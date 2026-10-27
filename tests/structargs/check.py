#!/usr/bin/env python3
"""A structure passed by value goes on the stack, not in a register (scripts/tools/equiv.py prototypes, stack_args, definitions).
SHC passes a struct argument in the caller's outgoing stack area, in parameter order with the integer arguments past the fourth;
the registers carry only the scalar arguments. Counting it as an integer register made the checker compare r4 (a leftover) on Crazy
Taxi kmiInitPAL / kmiInitNTSC -> kmiSetVideoTimings(KmVideoTimings) and missed the stack words. No game data, no compiler. Stdlib only.

    check.py      a temp C file with typedef'd structures:
                    alone      f(T252 t): no register argument, stack words compared (4, the cap)
                    mixed      g(int a, P3 p, float s): one integer and one float register, the point's 3 words on the stack
                    nested     h(int a, int b, Prop q) with Prop { int pad; P3 pos; }: two registers, 4 stack words
                    pointer    k(P3 *p): a pointer is a register, as before
                    scalars    m(int a, int b, int c, int d, int e): the fifth integer on the stack, as before
                    shorts     q(int, int, AngleR, float, int *) with AngleR { short x, y, z; }: 6 bytes = 2 stack words, three
                               integer registers (the pointer is the third) and one float; w(CS) with { char; short } is 1 word
                    defs       definitions() of the same functions in src/ agree (its integer count is not capped)
                    leftovers  a call is compared on the registers the callee's definition takes, whatever the caller's file declares:
                               more there (f(int, int, int, int)) or no prototype at all (g) compared registers the callee never reads,
                               leftovers (Virtua Tennis effFootDust -> vecSub(Stk5), screenSegVisible -> camWorldToView(Stk4): r4 a
                               stack pointer in the original, 0 in the C); fewer there (m(int, int)) is still raised to the definition
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401
import equiv  # noqa: E402

SRC = '''typedef struct { int w[63]; } T252;
typedef struct { float x, y, z; } P3;
typedef struct { int pad; P3 pos; } Prop;
typedef struct { short x, y, z; } AngleR;
typedef struct { char c; short s; } CS;

int f(T252 t);
int g(int a, P3 p, float s);
int h(int a, int b, Prop q);
int k(P3 *p);
int m(int a, int b, int c, int d, int e);
int q(int a, int b, AngleR r, float f, int *p);
int w(CS c);

int f(T252 t) { return t.w[0]; }
int g(int a, P3 p, float s) { return a; }
int h(int a, int b, Prop q) { return a; }
int k(P3 *p) { return 0; }
int m(int a, int b, int c, int d, int e) { return e; }
int q(int a, int b, AngleR r, float f, int *p) { return a; }
int w(CS c) { return 0; }
'''

WANT_REGS = {'f': (0, 0), 'g': (1, 1), 'h': (2, 0), 'k': (1, 0), 'm': (4, 0), 'q': (3, 1), 'w': (0, 0)}
WANT_STACK = {'f': 4, 'g': 3, 'h': 4, 'k': 0, 'm': 1, 'q': 2, 'w': 1}
WANT_DEFS = dict(WANT_REGS, m=(5, 0))                 # definitions() keeps the raw integer count; compared_arity caps it at 4


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    cwd = os.getcwd()
    try:
        os.makedirs(os.path.join(tmp, 'src'))
        path = os.path.join(tmp, 'src', 'structs.c')
        open(path, 'w').write(SRC)
        os.chdir(tmp)
        pro = equiv.prototypes(path)
        st = equiv.stack_args(path)
        de = equiv.definitions()
        for n, want in WANT_REGS.items():
            if tuple(pro.get(n, ())[:2]) != want:
                bad.append('%s registers: %r, want %r' % (n, pro.get(n), want))
            if st.get(n, 0) != WANT_STACK[n]:
                bad.append('%s stack words: %r, want %r' % (n, st.get(n), WANT_STACK[n]))
            if tuple(de.get(n, ())[:2]) != WANT_DEFS[n]:
                bad.append('%s definition registers: %r, want %r' % (n, de.get(n), WANT_DEFS[n]))
            if len(de.get(n, ())) > 2 and min(de[n][2], 4) != WANT_STACK[n]:
                bad.append('%s definition stack words: %r, want %r' % (n, de[n][2], WANT_STACK[n]))
        caller = os.path.join(tmp, 'src', 'caller.c')
        open(caller, 'w').write('int f(int, int, int, int);\nint m(int, int);\nint use(void) { return f(1, 2, 3, 4) + m(1, 2); }\n')
        table = {n: 0x8C010000 + 0x100 * i for i, n in enumerate(sorted(WANT_REGS))}
        ar, _ = equiv.compared_arity(caller, table)
        for n, want in (('f', (0, 0)), ('g', (1, 1)), ('m', (4, 0))):
            got = ar.get(0x0C000000 | (table[n] & 0x1FFFFFFF))
            if got != want:
                bad.append('leftovers: %s compared on %r registers, want %r (its definition)' % (n, got, want))
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp)
    for b in bad:
        print('FAIL', b)
    print('structargs: %s' % ('OK' if not bad else '%d failures' % len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
