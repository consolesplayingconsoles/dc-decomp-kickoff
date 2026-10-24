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


def main():
    bad = []
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
