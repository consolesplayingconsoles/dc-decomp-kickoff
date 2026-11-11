#!/usr/bin/env python3
"""split_asm.py writes a piece only when its text changes (scripts/tools/1-2-baseline/split_asm.py). build.sh and movecheck.py
assemble a piece whose source is newer than its object: a rerun after one entry changed in functions.txt rewrote every Zombie Revenge
piece, so every one looked changed. No game data, no compiler. Stdlib only.

    check.py      same     a second run with the same functions.txt leaves every piece untouched (its time does not move)
                  split    after one entry is split in two, the pieces it became are written and the others stay untouched
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(bytes(range(64)))
        open(os.path.join(tmp, 'BASE'), 'w').write('0C010000\n')
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F 0c010000 16 f1\nF 0c010010 32 f2\nF 0c010030 16 f3\n')
        run = lambda: subprocess.run([sys.executable, 'tools/1-2-baseline/split_asm.py', '1ST_READ.BIN', '0C010000', 'functions.txt', '.'],
                                     cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        run()
        asm = os.path.join(tmp, 'asm')
        old = time.time() - 1000
        for f in os.listdir(asm):
            os.utime(os.path.join(asm, f), (old, old))
        run()
        moved = [f for f in os.listdir(asm) if os.path.getmtime(os.path.join(asm, f)) > old + 1]
        if moved:
            bad.append('same: a rerun with the same listing rewrote %s' % moved)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F 0c010000 16 f1\nF 0c010010 16 f2\nF 0c010020 16 FUN_0c010020\nF 0c010030 16 f3\n')
        run()
        moved = sorted(f for f in os.listdir(asm) if os.path.getmtime(os.path.join(asm, f)) > old + 1)
        if moved != ['0c010010_f2.src', '0c010020_FUN_0c010020.src']:
            bad.append('split: want only the two halves of f2 written, got %s' % moved)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for b in bad:
        print('FAIL', b)
    print('splitasm: %s' % ('OK' if not bad else '%d failures' % len(bad)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
