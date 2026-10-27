#!/usr/bin/env python3
"""Directed cases never poke the function's own bytes (scripts/tools/5-generated/gen_equiv/directed.py apply): a value the original
loads from inside its own range (a constant in its literal pool, read with mov.l @(disp,pc) or mova + fmov.s) is part of the code, not
an input. Poking it changes the original only (the C keeps its own copy of the constant), so the case compares two programs and a right
C differs. Seen on Crazy Taxi Psg_Execute (-6.0 at 0C06DF74 poked to 1.0) and PutCourse_CheckPiece. No game data, no compiler.
Stdlib only.

    check.py      apply() with the function at 0C06D9C4..0C06E246:
                    pool       a float or int word inside the range: no case (None)
                    overlap    a word that starts before the range and ends inside it: no case
                    data       a word outside the range (at the end exactly, or in RAM): poked as before
                    regs       an argument or a call answer: set as before
                    second     the values tried for a compare's second operand flip it: fcmp/gt fr2,fr3 with fr3 = 1.0 and fr2 a
                               loaded float needs fr2 >= 1.0; the loop swapped the operands before asking, got -1.0 and the branch
                               stayed (Virtua Tennis cpuSglHitCheck: Ball+48 must be at least 1.0, its cases ran 28 of 3,284
                               instructions)
                    retkind    a function that differs on the directed cases in its return value only is written again with the
                               other return kinds, and the first that passes stays, its prototype in the file with it; when none
                               passes, the file is as it was (cpuSglHitCheck, cpuDblHitCheck: written void on cases that never
                               reached a return, the original returns a float there)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401
import directed  # noqa: E402

START, END = 0x0C06D9C4, 0x0C06E246
CASE = {'regs': {'r4': '0C800000', 'fr4': 2.5}, 'poke': {'0C900000': '00000000'}}


def retkind_case():
    import tempfile
    bad = []
    d = tempfile.mkdtemp(); p = os.path.join(d, 'gen_x.c')
    head = '/* scratch */\nint other(int);\nvoid hitfn(int a4);\n\n'
    body = 'void hitfn(int a4)\n{\n    other(a4);\n}\n'
    open(p, 'w').write(head + body + '\nint other(int a4)\n{\n    return a4;\n}\n')
    built = {'r0': 'int hitfn(int a4)\n{\n    return other(a4);\n}', 'fr0': 'float hitfn(int a4)\n{\n    return 2.5f;\n}',
             'void': 'void hitfn(int a4)\n{\n    other(a4);\n}'}
    tried = []
    def check():
        t_ = open(p).read(); tried.append(t_)
        return 'return 2.5f;' in t_
    if not directed.out_only('hitfn                        DIFFERS     case 23: out: original ["40200000"] / C ["00000000"]'):
        bad.append('retkind: a difference in the return value alone is not recognised')
    if directed.out_only('hitfn                        DIFFERS     case 2: calls: original [] / C []'):
        bad.append('retkind: a difference in the calls is taken for a return value')
    v = directed.retry_returns('hitfn', p, lambda n, k: built[k], check)
    t_ = open(p).read()
    if v != 'fr0' or 'float hitfn(int a4);' not in t_ or 'float hitfn(int a4)\n{\n    return 2.5f;' not in t_ or 'int other(int a4)' not in t_:
        bad.append('retkind: chose %r, file:\n%s' % (v, t_))
    open(p, 'w').write(head + body)
    v = directed.retry_returns('hitfn', p, lambda n, k: built[k], lambda: False)
    if v is not None or open(p).read() != head + body:
        bad.append('retkind: nothing passed but the file changed or a kind was chosen: %r' % v)
    return bad


def main():
    bad = retkind_case()
    for kind, a, b in (('fgt', 1.0, 0.0), ('fgt', 1.0, 5.0), ('gt', 10, 3), ('hs', 2, 7)):
        now = directed.result(kind, a, b) if kind not in ('feq', 'fgt') else (a > b)
        got = directed.flip_values(kind, 'b', a, b)
        flips = [c for c in got if (((a > c) if kind == 'fgt' else directed.result(kind, a, c)) != now)]
        if not got or flips != got:
            bad.append('second: %s %r > %r, values for the second operand %r, of which only %r flip it' % (kind, a, b, got, flips))
        got = directed.flip_values(kind, 'a', a, b)
        flips = [c for c in got if (((c > b) if kind == 'fgt' else directed.result(kind, c, b)) != now)]
        if not got or flips != got:
            bad.append('second: %s first operand values %r, of which only %r flip it' % (kind, got, flips))
    directed.CTX['range'] = (START, END)
    if directed.apply(CASE, ('fmem', 0x0C06DF74, 4, 0), -7.0) is not None:
        bad.append('pool: a float constant inside the function was poked')
    if directed.apply(CASE, ('mem', 0x0C06DF74, 4, 0, 0), 1) is not None:
        bad.append('pool: an int word inside the function was poked')
    if directed.apply(CASE, ('mem', START - 2, 4, 0, 0), 1) is not None:
        bad.append('overlap: a word ending inside the function was poked')
    c = directed.apply(CASE, ('mem', END, 4, 0, 0), 5)
    if not c or c['poke'].get('%08X' % END) != '05000000':
        bad.append('data: the word right after the function was not poked: %r' % (c and c.get('poke')))
    c = directed.apply(CASE, ('fmem', 0x0C910000, 4, 0), 1.0)
    if not c or c['poke'].get('0C910000') != '0000803f':
        bad.append('data: a float in RAM was not poked: %r' % (c and c.get('poke')))
    if CASE['poke'] != {'0C900000': '00000000'}:
        bad.append('the case given was changed')
    c = directed.apply(CASE, ('arg', 5, 0), 3)
    if not c or c['regs'].get('r5') != '00000003':
        bad.append('regs: an argument was not set: %r' % (c and c.get('regs')))
    c = directed.apply(CASE, ('call', 1, True, 0), -7.0)
    if not c or c['calls'][1].get('fr0') != 'C0E00000':
        bad.append('regs: a float call answer was not set: %r' % (c and c.get('calls')))
    for b in bad:
        print('FAIL', b)
    print('directed: %s' % ('OK' if not bad else '%d failures' % len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
