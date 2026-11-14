#!/usr/bin/env python3
"""C that calls a function without an argument the original gives it (scripts/tools/consistency.py, short_calls; the check itself is
scripts/tools/8-build/protocheck.py scan_lost). Virtua Tennis uniformPreviewFree called nlObjPutFreeTextureOnce() under an old prototype
`(void)` after the callee was found to take the model in r4: Exhibition went black on the console once the court was picked, and the
proof passed, the call being compared on the caller's own prototype. charaTexReloadAll and strmBgmFadeOut were the same, and Zombie
Revenge's item markers (drawn with no size). No compiler. Stdlib only.

    check.py      a temp repo with a 0x110-byte executable assembled here by hand: g at 8c010100 and four callers of it, each
                  `<first> ; mov.l @(pool,pc),r3 ; jsr @r3 ; nop ; rts ; nop ; pool`; src/gen_g.c defines `int g(int a4)`:
                    f_short  first is `mov #5,r4`; src/gen_a.c prototypes `int g(void);` and calls g():   reported as `short call`
                    f_noset  first is `nop`; the same file, the same call:                                 not reported (the original gives no r4)
                    f_full   first is `mov #5,r4`; src/gen_b.c prototypes `int g(int);` and calls g(5):   not reported
                    f_hand   as f_short, in src/hand.c (written by hand):                                  reported
                  --fix drops f_short with its cases and its line in tests/equivalent.txt, keeps f_noset, f_full and g, and leaves
                  f_hand where it is (listed, for its author); a second run still lists f_hand and nothing else
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', 'consistency.py')

FUNCTIONS = "F 8c010000 16 f_short\nF 8c010020 16 f_noset\nF 8c010040 16 f_full\nF 8c010060 16 f_hand\nF 8c010100 4 g\n"
FILES = {'gen_a': "int g(void);\nint f_short(void)\n{\n    return g();\n}\nint f_noset(void)\n{\n    return g();\n}\n",
         'gen_b': "int g(int);\nint f_full(void)\n{\n    return g(5);\n}\n",
         'gen_g': "int g(int a4)\n{\n    return a4;\n}\n",
         'hand': "int g(void);\nint f_hand(void)\n{\n    return g();\n}\n"}
HOME = {'f_short': 'gen_a', 'f_noset': 'gen_a', 'f_full': 'gen_b', 'f_hand': 'hand', 'g': 'gen_g'}


def run(repo, *args):
    r = subprocess.run([sys.executable, TOOL] + list(args), cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=120)
    return r.stdout


def main():
    repo = tempfile.mkdtemp(prefix='consistency_short_')
    try:
        b = bytearray(0x110)
        for off, first in ((0x00, 0xE405), (0x20, 0x0009), (0x40, 0xE405), (0x60, 0xE405)):     # mov #5,r4 / nop
            struct.pack_into('<6HI', b, off, first, 0xD302, 0x430B, 0x0009, 0x000B, 0x0009, 0x8C010100)
        struct.pack_into('<2H', b, 0x100, 0x000B, 0x6043)                                         # g: rts ; mov r4,r0
        open(os.path.join(repo, '1ST_READ.BIN'), 'wb').write(bytes(b))
        open(os.path.join(repo, 'BASE'), 'w').write('8c010000\n')
        open(os.path.join(repo, 'functions.txt'), 'w').write(FUNCTIONS)
        for d in ('src', 'state'):
            os.makedirs(os.path.join(repo, d))
        for stem, text in FILES.items():
            open(os.path.join(repo, 'src', stem + '.c'), 'w').write(text)
        for n, stem in HOME.items():
            os.makedirs(os.path.join(repo, 'tests', stem), exist_ok=True)
            open(os.path.join(repo, 'tests', stem, n + '.json'), 'w').write('{}')
        open(os.path.join(repo, 'tests', 'equivalent.txt'), 'w').write(''.join(n + '\n' for n in sorted(HOME)))
        out = run(repo)
        line = next((l for l in out.splitlines() if l.startswith('short call')), '')
        names = line.split(None, 3)[3].replace(',', ' ').split() if len(line.split(None, 3)) > 3 else []
        assert sorted(names) == ['f_hand', 'f_short'], 'the calls that lost an argument are not the ones reported:\n' + out
        fixed = run(repo, '--fix')
        text = open(os.path.join(repo, 'src', 'gen_a.c')).read()
        assert 'int f_short' not in text and 'int f_noset' in text, '--fix does not drop the short caller alone:\n' + fixed
        assert not os.path.exists(os.path.join(repo, 'tests', 'gen_a', 'f_short.json')), '--fix leaves the cases of f_short'
        assert open(os.path.join(repo, 'tests', 'equivalent.txt')).read().split() == ['f_full', 'f_hand', 'f_noset', 'g'], '--fix leaves the proof of f_short'
        assert 'int f_hand' in open(os.path.join(repo, 'src', 'hand.c')).read() and not os.path.exists(os.path.join(repo, 'partial')), \
            '--fix moves C written by hand'
        assert 'f_hand' in fixed and 'written by hand' in fixed, '--fix does not say the hand-written caller is left:\n' + fixed
        out = run(repo)
        line = next((l for l in out.splitlines() if l.startswith('short call')), '')
        assert line.split()[2] == '1' and 'f_hand' in line and out.splitlines()[-1] == '1 out of step', 'a second run does not list f_hand alone:\n' + out
        print('[consistency_short] ok: a call without an argument the original sets is reported; generated C is dropped with its cases and proof, hand-written C is listed and left')
    finally:
        shutil.rmtree(repo, ignore_errors=True)


if __name__ == '__main__':
    main()
