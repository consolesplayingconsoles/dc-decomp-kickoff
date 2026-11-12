#!/usr/bin/env python3
"""The mode of a project (`MODE: equivalent` or `MODE: matching` in status.txt, scripts/tools/progress.py) and the overlay report that
only a game with code overlays gets. An older repo has no MODE line and no overlays.tsv: its report must come out as it always did.
No game data, no compiler. Stdlib only.

    check.py      a temp repo with two functions of 8 bytes: alpha is a matching unit (src/a.c), beta has equivalent C proven by cases:
                    default    no MODE line: the equivalent report (its pipeline rows, no matching row), as before the modes existed
                    explicit   `MODE: equivalent` gives the same report as no line at all
                    matching   `MODE: matching`: only the unit counts (the cases of the other function do not), no equivalent pipeline rows
                    invalid    any other word stops with an error naming the two modes, nothing is guessed
                    overlays   without overlays.tsv the report has no OVERLAYS section; with it, the overlay report follows the main one
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
CODE = struct.pack('<16H', *([0x000B, 0x0009] * 8))


def run(tmp, status):
    w = lambda p, t: open(os.path.join(tmp, p), 'w').write(t)
    w('functions.txt', 'F %08x 8 alpha\nF %08x 8 beta\n' % (BASE, BASE + 8))
    w('tests/equivalent.txt', 'beta\n')
    w('src/a.c', '/* @unit %08X-%08X */\nvoid alpha(void) {}\n' % (BASE, BASE + 8))      # a matching unit over alpha
    if status is None:
        if os.path.exists(os.path.join(tmp, 'status.txt')):
            os.remove(os.path.join(tmp, 'status.txt'))
    else:
        w('status.txt', status)
    r = subprocess.run([sys.executable, 'tools/progress.py'], cwd=tmp, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(CODE)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        os.makedirs(os.path.join(tmp, 'tests'))
        os.makedirs(os.path.join(tmp, 'src'))

        rc0, none = run(tmp, None)
        rc1, eq = run(tmp, 'MODE: equivalent\n')
        if rc0 or rc1:
            bad.append('default/explicit: progress.py stopped:\n%s' % (none if rc0 else eq)[-500:])
        elif none != eq:
            bad.append('explicit: `MODE: equivalent` and no MODE line give different reports')

        left = lambda t: (lambda m: m.groups() if m else (None, None))(re.search(r'FUNCTIONS LEFT\s+\(\s*([\d.]+)% complete\)\s+(\d+)', t))
        rc, mt = run(tmp, 'MODE: matching\n')
        if rc or left(mt) != ('50.0', '1'):
            bad.append('matching: 1 of 2 left (only the unit is done, beta\'s cases do not count): %s\n%s' % (left(mt), mt[-400:]))
        if left(eq) != ('100.0', '0'):
            bad.append('explicit: equivalent mode counts the unit and the proven function, 0 left: %s\n%s' % (left(eq), eq[-400:]))
        if 'Not written C' not in eq or 'Not written C' in mt:
            bad.append('matching: the equivalent pipeline rows ("Not written C" ...) belong to the equivalent report only')

        rc, err = run(tmp, 'MODE: sloppy\n')
        if rc == 0 or 'equivalent' not in err or 'matching' not in err:
            bad.append('invalid: an unknown mode was accepted or the error does not name the two modes: %r' % err[-300:])

        rc, plain = run(tmp, None)
        if 'OVERLAYS' in plain:
            bad.append('overlays: a game without overlays.tsv got an overlay report')
        open(os.path.join(tmp, 'overlays.tsv'), 'w').write('name\tbase\thash\tstatus\n')
        rc, withov = run(tmp, None)
        if rc or not withov.startswith(plain.rstrip('\n')) or 'OVERLAYS' not in withov:
            bad.append('overlays: with overlays.tsv the overlay report should follow the unchanged main report:\n' + withov[-500:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        print('[progress_mode] FAIL\n' + '\n'.join(bad))
        sys.exit(1)
    print('[progress_mode] ok: no MODE line is the equivalent report, matching and an unknown mode behave as documented, overlays add a section only when overlays.tsv exists')


main()
