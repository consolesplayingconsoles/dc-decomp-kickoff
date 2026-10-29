#!/usr/bin/env python3
"""Two tools may work in one repo at a time (a shrink and another shrink, a generator run and a build): a file of src/ can be removed or
rewritten between the moment equiv.py lists src/*.c and the moment it reads it. definitions() and used_definitions() read every src/*.c
for the functions' parameters; a file that is gone made them raise, equiv.py printed nothing, and shrink.py took a function that had
passed for one that differed and put the old C back (Virtua Tennis, two shrinks in parallel: 25 functions "failed" in their written file and
12 were left without a recorded pass). A vanished file is skipped. No game data. Stdlib only.

    check.py      a temp repo with src/a.c; the glob also names src/gone.c, which does not exist:
                    defs      definitions() returns a's functions and does not raise
                    used      used_definitions() does too
"""
import glob
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')


def main():
    tmp = tempfile.mkdtemp()
    try:
        os.chdir(tmp)
        os.makedirs('src')
        open('src/a.c', 'w').write('int f(int a4, int a5)\n{\n    return a4 + a5;\n}\n')
        open('1ST_READ.BIN', 'wb').write(b'\x09\x00' * 16)
        open('BASE', 'w').write('0C010000\n')
        open('functions.txt', 'w').write('F 0c010000 8 f\n')
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import equiv
        real = glob.glob
        equiv.glob.glob = lambda pat, *a, **k: real(pat, *a, **k) + ([os.path.join('src', 'gone.c')] if 'src' in pat else [])
        bad = []
        try:
            d = equiv.definitions()
            if 'f' not in d:
                bad.append('defs: f is not found in %s' % sorted(d))
        except OSError as e:
            bad.append('defs: raised %s' % e)
        try:
            equiv._USED.clear()
            u = equiv.used_definitions()
            if 'f' not in u:
                bad.append('used: f is not found in %s' % sorted(u))
        except OSError as e:
            bad.append('used: raised %s' % e)
        if bad:
            sys.exit('[ERROR] concurrent check failed:\n' + '\n'.join(bad))
        print('[concurrent] ok: a src file that vanishes between the listing and the read is skipped by definitions() and used_definitions()')
    finally:
        os.chdir('/')
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
