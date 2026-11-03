#!/usr/bin/env python3
"""STACKFUZZ=<seed> equiv.py runs a function's cases again with distinct nonzero words at the entry stack (scripts/tools/equiv.py).
No game data, no compiler. Stdlib only.

The cases hold zeros in the words past the declared parameters, where a C that reads its own frame for a word the caller pushed gives the
same answer as the original, so a function declared with one stack word that reads a three-float vector passed every case (Virtua Tennis
shadowBallDraw, primFrameCorners, standPanelDraw, cpuInRange, hudBarDraw, the select-panel call: the shadow did not follow the ball, panels
drew at no position, the score and a green block showed).

    check.py      the words fuzz_words gives:
                    count     24 words
                    nonzero   none is 0 (a zero is what the plain cases already hold)
                    same      the same seed, function and case give the same words
                    differ    another case, function or seed gives other words
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))


def main():
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, equiv\n"
                  "a = equiv.fuzz_words('1', 'f', 3)\n"
                  "print('count', len(a))\nprint('nonzero', all(a))\nprint('same', a == equiv.fuzz_words('1', 'f', 3))\n"
                  "print('differ', a != equiv.fuzz_words('1', 'f', 4) and a != equiv.fuzz_words('1', 'g', 3) and a != equiv.fuzz_words('2', 'f', 3))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout
        got = dict(l.split(' ', 1) for l in out.strip().split('\n') if ' ' in l)
        bad = ['%s: %s' % (k, got.get(k)) for k, w in (('count', '24'), ('nonzero', 'True'), ('same', 'True'), ('differ', 'True')) if got.get(k) != w]
        if bad:
            sys.exit('[ERROR] stackfuzz check failed:\n' + '\n'.join(bad) + '\n' + out[-400:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('[stackfuzz] ok: the entry-stack words are 24 nonzero ones, fixed by seed, function and case')


if __name__ == '__main__':
    main()
