#!/usr/bin/env python3
"""Generated C proven while functions.txt gave the function a short size (scripts/tools/consistency.py). The size was fixed later (code past
a literal pool in the middle of the body), the proof stayed in tests/equivalent.txt, and the C still calls the address that is now inside the
function itself: the current checker fails it (Virtua Tennis, 113 functions: kmiConvertUVnum's `bra 0x8c0ea608` was written as a call to
0x8C0EA608). No game data, no compiler. Stdlib only.

    check.py      a temp repo: functions.txt with three functions, src/gen_a.c defining them, cases and tests/equivalent.txt for each:
                    f_stale  calls an address inside its own span:  reported as `stale size`
                    f_ext    calls the address of another function:  not reported
                    f_plain  calls nothing:                          not reported
                  --fix drops f_stale's C, its cases and its line in tests/equivalent.txt (the generator writes it again) and keeps the others;
                  a second run reports consistent
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', 'consistency.py')

FUNCTIONS = "F 8c010000 64 f_stale\nF 8c010100 32 f_plain\nF 8c010200 32 f_ext\n"
C = """int f_stale(int a4)
{
    return ((int (*)(int))(0x8C010030))(a4);
}
int f_plain(int a4)
{
    return a4 + 1;
}
int f_ext(int a4)
{
    return ((int (*)(int))(0x8C010100))(a4);
}
"""


def run(repo, *args):
    r = subprocess.run([sys.executable, TOOL] + list(args), cwd=repo, capture_output=True, text=True, timeout=120)
    return r.stdout + r.stderr


def main():
    repo = tempfile.mkdtemp(prefix='consistency_span_')
    try:
        for d in ('src', 'state', 'tests/gen_a'):
            os.makedirs(os.path.join(repo, d))
        open(os.path.join(repo, 'functions.txt'), 'w').write(FUNCTIONS)
        open(os.path.join(repo, 'src', 'gen_a.c'), 'w').write(C)
        open(os.path.join(repo, 'tests', 'equivalent.txt'), 'w').write('f_stale\nf_plain\nf_ext\n')
        for n in ('f_stale', 'f_plain', 'f_ext'):
            open(os.path.join(repo, 'tests', 'gen_a', n + '.json'), 'w').write('{}')
        out = run(repo)
        line = next((l for l in out.splitlines() if l.startswith('stale size')), '')
        assert 'f_stale' in line, 'f_stale (calls an address inside itself) is not reported:\n' + out
        assert 'f_plain' not in line and 'f_ext' not in line, 'a function that does not call into itself is reported:\n' + out
        out = run(repo, '--fix')
        text = open(os.path.join(repo, 'src', 'gen_a.c')).read()
        assert 'f_stale' not in text, '--fix leaves the stale C in src/gen_a.c'
        assert 'f_plain' in text and 'f_ext' in text, '--fix removes a function it should keep'
        assert not os.path.exists(os.path.join(repo, 'tests', 'gen_a', 'f_stale.json')), '--fix leaves the stale cases'
        assert open(os.path.join(repo, 'tests', 'equivalent.txt')).read().split() == ['f_plain', 'f_ext'], '--fix leaves the stale proof in tests/equivalent.txt'
        assert 'consistent' in run(repo).splitlines()[-1], 'a second run is not consistent'
        print('[consistency_span] ok: C that calls an address inside its own function is reported, dropped with its cases and proof; the others stay')
    finally:
        shutil.rmtree(repo, ignore_errors=True)


main()
