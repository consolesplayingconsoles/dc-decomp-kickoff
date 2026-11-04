#!/usr/bin/env python3
"""Hand cases for a function the random draw cannot cover (scripts/tools/6-agentic/casesearch.py). No game data, no compiler. Stdlib only.

The drawn cases fill memory with random words, and a function that tests a game mode word only ever sees the one path (Virtua Tennis
shadowBallDraw: 19% covered, its other path ran only for modes 1, 4, 7, 8, 10 and 14). casesearch reads which RAM words the original reads,
and which small integers its own code compares against, and sets those words to them.

    check.py      a temp repo with one function, `if (*(int *)0x0C100000 == 77) return 2; return 1;`:
                    both      the kept cases run the original through both returns (the word set to 77 in one, not in another)
                    pool      the literal pool inside the function is not changed by any kept case (a case that rewrites the constant
                              0x0C100000 calls a different word and the function reads garbage)
                    file      cases-hand/f.json is written, and every case in it finishes on the original
                    code      a function reads a word that lies in layout.txt's `code` region but outside its own bytes (a jump table
                              inside a library helper: Virtua Tennis camMoveBeginAtGoal, whose block copy goes through _quick_odd_mvn):
                              no kept case pokes any address of that region. A poked jump table made the original copy 48 bytes for 12,
                              and every case of the function then DIFFERED from the C, which does not call the helper
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
# mov.l @(4,pc),r1 / mov.l @r1,r0 / cmp/eq #77,r0 / bt +2 / mov #1,r0 / rts / nop / mov #2,r0 / rts / nop, then the pool word
WORDS = [0xD104, 0x6012, 0x884D, 0x8902, 0xE001, 0x000B, 0x0009, 0xE002, 0x000B, 0x0009]
POOL = 0x0C100000
RET1, RET2 = BASE + 8, BASE + 14                 # the two `mov #n,r0` instructions
TABLE = BASE + 0x300                             # a word in the code region, far outside the function's own bytes and the 512 after them
TABLE_WORDS = [0xD104, 0x6012, 0x884D, 0x8902, 0xE001, 0x000B, 0x0009, 0xE002, 0x000B, 0x0009]    # as WORDS, reading TABLE


def code_region(tmp):
    """The `code` scenario: g reads TABLE, a word of the image inside layout.txt's code region. Returns [] or the problems."""
    code = b''.join(struct.pack('<H', w) for w in TABLE_WORDS) + struct.pack('<I', TABLE)
    image = code + b'\x00' * (TABLE - BASE - len(code)) + struct.pack('<I', 77)
    open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(image)
    open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
    open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d g\n' % (BASE, len(code)))
    open(os.path.join(tmp, 'layout.txt'), 'w').write('game 0C010000 0C020000\ncode 0C010000 0C010400\n')
    r = subprocess.run([sys.executable, 'tools/6-agentic/casesearch.py', 'g', '150', '12'], cwd=tmp, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, universal_newlines=True)
    path = os.path.join(tmp, 'cases-hand', 'g.json')
    if not os.path.exists(path):
        return ['code: no cases-hand/g.json:\n' + r.stdout[-400:]]
    cases = json.load(open(path))
    if not cases:
        return ['code: no case kept']
    hits = sorted({k for c in cases for k in c.get('poke', {}) if BASE <= int(k, 16) < BASE + 0x400})
    return ['code: kept cases poke the code region (%s)' % ', '.join(hits[:4])] if hits else []


def main():
    tmp = tempfile.mkdtemp()
    bad = []
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        code = b''.join(struct.pack('<H', w) for w in WORDS) + struct.pack('<I', POOL)
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d f\n' % (BASE, len(code)))
        open(os.path.join(tmp, 'layout.txt'), 'w').write('game 0C010000 0C020000\ncode 0C010000 0C010100\n')
        r = subprocess.run([sys.executable, 'tools/6-agentic/casesearch.py', 'f', '150', '12'], cwd=tmp, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, universal_newlines=True)
        path = os.path.join(tmp, 'cases-hand', 'f.json')
        if not os.path.exists(path):
            sys.exit('[ERROR] casesearch check failed: no cases-hand/f.json:\n' + r.stdout[-500:])
        cases = json.load(open(path))
        script = ("import sys, json; sys.path.insert(0, 'tools'); import toolpath, sh4sim\n"
                  "cases = json.load(open('cases-hand/f.json')); seen = set(); fin = 0; pool = 0\n"
                  "for c in cases:\n"
                  "    c = dict(c, exe='1ST_READ.BIN', base='%08X', entry='%08X', end='%08X', steps=10000)\n"
                  "    r = sh4sim.run(c, '.')\n"
                  "    if not r['error']: fin += 1\n"
                  "    seen |= set(r.get('covered', []))\n"
                  "    if any(int(a, 16) in range(%d, %d) for a in c.get('poke', {})): pool += 1\n"
                  "print('FIN', fin, len(cases)); print('RET1', %d in seen); print('RET2', %d in seen); print('POOL', pool)\n"
                  % (BASE, BASE, BASE + len(code), BASE, BASE + len(code), RET1, RET2))
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout
        got = {l.split(' ')[0]: l.split(' ')[1:] for l in out.strip().split('\n') if l}
        if got.get('RET1') != ['True'] or got.get('RET2') != ['True']:
            bad.append('both: the kept cases do not reach both returns (%s)' % out.strip()[-300:])
        if got.get('POOL') != ['0']:
            bad.append('pool: a kept case writes into the function\'s own bytes (%s)' % got.get('POOL'))
        if not got.get('FIN') or got['FIN'][0] != got['FIN'][1]:
            bad.append('file: a kept case does not finish on the original (%s)' % got.get('FIN'))
        tmp2 = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp2, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
            bad += code_region(tmp2)
        finally:
            shutil.rmtree(tmp2, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] casesearch check failed:\n' + '\n'.join(bad))
    print('[casesearch] ok: the search finds the value a branch tests, reaches both paths, and leaves the function\'s own pool and the code region alone')


if __name__ == '__main__':
    main()
