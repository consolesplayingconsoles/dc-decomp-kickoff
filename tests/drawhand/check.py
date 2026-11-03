#!/usr/bin/env python3
"""What gen_equiv --draw (draw_cases.py) does with the function's parameters and with cases supplied by hand. No game data, no compiler.
Stdlib only.

    check.py      a temp repo with two synthetic functions and their C:
                    stackarg  `rd` pushes r14 and reads a word 124 bytes above its frame, the caller's, then returns it. Drawn from the C
                              `int rd(int a4)` (no stack parameter) a case that makes the original read there is no case (it reads what
                              its caller owns), so nothing is drawn; from `int rd(int a4, int a5, int a6, int a7, int a8)` (it takes
                              stack words) the same original gets cases
                    hand      `tst` returns 2 when the word at 0C100000 is 77, else 1. The drawn memory is zeros or random, so it
                              reaches one return; with cases-hand/tst.json holding one case with the word set to 77 and one without,
                              the cases written to tests/ run both returns
"""
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
BASE = 0x0C010000
RD = [0x2FE6, 0x61F3, 0x717C, 0x6012, 0x000B, 0x6EF6]      # mov.l r14,@-r15 / mov r15,r1 / add #124,r1 / mov.l @r1,r0 / rts / mov.l @r15+,r14
TST = [0xD104, 0x6012, 0x884D, 0x8902, 0xE001, 0x000B, 0x0009, 0xE002, 0x000B, 0x0009]    # as tests/casesearch: if (*(int *)POOL == 77) return 2; return 1;
POOL = 0x0C100000


def words(ws):
    return b''.join(struct.pack('<H', w) for w in ws)


def draw(tmp, c_text, name, extra=()):
    open(os.path.join(tmp, 'src', name + '.c'), 'w').write(c_text)
    out = subprocess.run([sys.executable, 'tools/5-generated/gen_equiv', '--draw', 'src/%s.c' % name, name, '--force'] + list(extra), cwd=tmp,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout
    return out, [l for l in out.split('\n') if l.startswith(name)]


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        rd = words(RD)
        rd += b'\x00' * ((4 - len(rd) % 4) % 4)
        tst = words(TST) + struct.pack('<I', POOL)
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(rd + tst)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d rd\nF %08x %d tst\n' % (BASE, len(rd), BASE + len(rd), len(tst)))
        open(os.path.join(tmp, 'layout.txt'), 'w').write('game 0C010000 0C020000\ncode 0C010000 0C010100\n')
        os.makedirs(os.path.join(tmp, 'src'))

        out, line = draw(tmp, 'int rd(int a4)\n{\n    return a4;\n}\n', 'rd')
        if not line or 'skipped' not in line[0]:
            bad.append('stackarg: with no stack parameter the reads above the frame must leave no case: %s\n%s' % (line, out[-400:]))
        out, line = draw(tmp, 'int rd(int a4, int a5, int a6, int a7, int a8)\n{\n    return a8;\n}\n', 'rd')
        if not line or 'cases' not in line[0] or 'skipped' in line[0]:
            bad.append('stackarg: with a stack parameter (a8) the same original must get cases: %s\n%s' % (line, out[-400:]))

        out, line = draw(tmp, 'int tst(int a4)\n{\n    return a4;\n}\n', 'tst')
        plain = os.path.join(tmp, 'tests', 'tst', 'tst.json')
        os.makedirs(os.path.join(tmp, 'cases-hand'), exist_ok=True)
        hand = [{'regs': {}, 'poke': {'%08X' % POOL: struct.pack('<I', 77).hex()}, 'calls': [], 'about': 'hand: word is 77'},
                {'regs': {}, 'poke': {'%08X' % POOL: struct.pack('<I', 5).hex()}, 'calls': [], 'about': 'hand: word is 5'}]
        json.dump(hand, open(os.path.join(tmp, 'cases-hand', 'tst.json'), 'w'))
        out, line = draw(tmp, 'int tst(int a4)\n{\n    return a4;\n}\n', 'tst')
        if not os.path.exists(plain):
            bad.append('hand: no tests/tst/tst.json written: %s\n%s' % (line, out[-400:]))
        else:
            d = json.load(open(plain))
            cases = d.get('dev', []) + d.get('holdout', [])
            run = ("import sys, json; sys.path.insert(0, 'tools'); import toolpath, sh4sim\n"
                   "d = json.load(open('tests/tst/tst.json')); seen = set()\n"
                   "for c in d.get('dev', []) + d.get('holdout', []):\n"
                   "    r = sh4sim.run(dict(c, exe='1ST_READ.BIN', base='%08X', entry='%08X', end='%08X', steps=10000), '.'); seen |= set(r.get('covered', []))\n"
                   "print('RET1', %d in seen); print('RET2', %d in seen)\n"
                   % (BASE, BASE + len(rd), BASE + len(rd) + len(tst), BASE + len(rd) + 8, BASE + len(rd) + 14))
            res = subprocess.run([sys.executable, '-c', run], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout
            if 'RET1 True' not in res or 'RET2 True' not in res:
                bad.append('hand: the written cases (%d) do not run both returns of tst:\n%s' % (len(cases), res[-300:]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] drawhand check failed:\n' + '\n'.join(bad))
    print('[drawhand] ok: a function without stack parameters gets no case that reads its caller\'s frame, one with them does; cases-hand/ cases reach the paths the draw cannot')


if __name__ == '__main__':
    main()
