#!/usr/bin/env python3
"""Naming and done are counted apart (scripts/tools/progress.py): a proven function is done with or without a name, and a function
called thunk_FUN_<address> has no name, like FUN_<address> (Crazy Taxi, 2026-10-31: the unnamed count missed its thunk_FUN_
functions). No game data, no compiler. Stdlib only.

    check.py      a temp repo with four functions, all proven (tests/equivalent.txt), two named and two not (FUN_ and thunk_FUN_):
                    done      FUNCTIONS LEFT is 0 and the share complete is 100.0%: a missing name never counts against done
                    unnamed   the unnamed row is 2: thunk_FUN_ counts as unnamed
                    named     naming the two makes the unnamed row 0
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
BASE = 0x8C010000
CODE = struct.pack('<16H', *([0x000B, 0x0009] * 8))                  # four functions of 8 bytes: rts / nop, twice


def report(tmp, names):
    open(os.path.join(tmp, 'functions.txt'), 'w').write(''.join('F %08x 8 %s\n' % (BASE + 8 * i, n) for i, n in enumerate(names)))
    open(os.path.join(tmp, 'tests', 'equivalent.txt'), 'w').write(''.join(n + '\n' for n in names))
    r = subprocess.run([sys.executable, 'tools/progress.py'], cwd=tmp, capture_output=True, text=True)
    return r.stdout + r.stderr


def left(out):
    m = re.search(r'FUNCTIONS LEFT\s+\(\s*([\d.]+)% complete\)\s+(\d+)', out)
    return (float(m.group(1)), int(m.group(2))) if m else None


def unnamed(out):
    m = re.search(r'^\s*unnamed\s+(\d+)', out, re.M)
    return int(m.group(1)) if m else None


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(CODE)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        os.makedirs(os.path.join(tmp, 'tests'))
        os.makedirs(os.path.join(tmp, 'src'))
        out = report(tmp, ['alpha', 'beta', 'FUN_8c010010', 'thunk_FUN_8c010000'])
        if left(out) != (100.0, 0):
            bad.append('done: %r, want (100.0, 0): proven functions without a name are done\n%s' % (left(out), out[-600:]))
        if unnamed(out) != 2:
            bad.append('unnamed: %r, want 2 (FUN_ and thunk_FUN_)\n%s' % (unnamed(out), out[-600:]))
        out = report(tmp, ['alpha', 'beta', 'gamma', 'thunk_alpha'])
        if unnamed(out) != 0:
            bad.append('named: unnamed is %r, want 0\n%s' % (unnamed(out), out[-600:]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] progress_named check failed:\n' + '\n'.join(bad))
    print('[progress_named] ok: a proven FUN_ function is done; thunk_FUN_ counts as unnamed')


if __name__ == '__main__':
    main()
