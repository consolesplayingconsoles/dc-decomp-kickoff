#!/usr/bin/env python3
"""Cases supplied by hand (scripts/tools/5-generated/gen_equiv/gen_drv.py hand_cases, used first by tests()), on files in a temp repo.
No game data, no compiler. Stdlib only.

Drawing finds no case that ends for a few functions whose loops end only on particular values (Virtua Tennis _div64: a 66-pass division;
emotFaceMorph: a loop that ends on a call answering -1), though a plain search over small values finds hundreds that do. Crazy Taxi
supplied such cases by hand. A file cases-hand/<name>.json in the decomp's root (a list of cases, or {dev, holdout}) is the candidate
pool for that function: the original is run on each, the ones it finishes on are picked by coverage, as for drawn candidates.

    check.py      file      a function with a file gets its cases; one without gets none
                  both      the {dev, holdout} form is read as one list
                  wired     tests() takes hand cases first and keeps them only when enough survive
"""
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
tmp = tempfile.mkdtemp()
os.chdir(tmp)
open('functions.txt', 'w').write('F 8c020000 64 fn\n')
open('BASE', 'w').write('8C020000\n')
open('1ST_READ.BIN', 'wb').write(b'\x00\x09' * 32)
sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401
import gen_drv  # noqa: E402


def main():
    bad = []
    try:
        none = gen_drv.hand_cases('f')
    except AttributeError:
        sys.exit('[ERROR] handcases check failed:\ngen_drv has no hand_cases()')
    os.makedirs('cases-hand')
    json.dump([{'about': 'a', 'regs': {'r4': '00000001'}}, {'about': 'b'}], open('cases-hand/f.json', 'w'))
    json.dump({'dev': [{'about': 'c'}], 'holdout': [{'about': 'd'}, {'about': 'e'}]}, open('cases-hand/g.json', 'w'))
    f, g, h = gen_drv.hand_cases('f'), gen_drv.hand_cases('g'), gen_drv.hand_cases('h')
    if none != [] or [c['about'] for c in f] != ['a', 'b'] or h != []:
        bad.append('file: no file %s, with a file %s, other %s' % (none, [c['about'] for c in f], h))
    if [c['about'] for c in g] != ['c', 'd', 'e']:
        bad.append('both: %s' % [c['about'] for c in g])
    src = open(os.path.join(TOOLS, '5-generated', 'gen_equiv', 'gen_drv.py')).read()
    body = re.search(r'^def tests\(.*?(?=^def |\Z)', src, re.M | re.S)
    text = body.group(0) if body else ''
    if not re.search(r'hand_cases\(name\).*?pick\(name,hc,36\)', text, re.S):
        bad.append('wired: tests() does not pick among the hand cases')
    if bad:
        sys.exit('[ERROR] handcases check failed:\n' + '\n'.join(bad))
    print('[handcases] ok: cases-hand/<name>.json is the candidate pool for that function')


if __name__ == '__main__':
    main()
