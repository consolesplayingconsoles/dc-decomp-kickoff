#!/usr/bin/env python3
"""C that addresses its stack-argument structure `StkN s` outside it (scripts/tools/consistency.py, args_outside). Below &s are the
registers the compiled function saved on entry, its return address among them; past its 4N bytes is the caller's frame. Zombie Revenge
FUN_0c0a6928, a hand draft, kept the original's locals at &s - 52 .. &s - 4 and wrote results at &s + 20 .. &s + 32 (a Stk4): it overwrote
its saved pr and the game ran the stack; three more functions had the same form. Their proofs passed: writes below the entry stack pointer
are not compared. No game data, no compiler. Stdlib only.

    check.py      a temp repo: functions.txt with four functions, src/gen_a.c defining them, cases and tests/equivalent.txt for each:
                    f_below  writes *(float *)((int)&s + -4):              reported as `args outside`
                    f_past   writes s.w[4] of a Stk4 and &s + 20:          reported
                    f_inside reads s.w[0..3] and &s + 12 of a Stk4:        not reported
                    f_none   no structure parameter:                       not reported
                  --fix drops f_below and f_past with their cases and their lines in tests/equivalent.txt and keeps the others;
                  a second run reports consistent
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', 'consistency.py')

FUNCTIONS = "F 8c010000 32 f_below\nF 8c010100 32 f_past\nF 8c010200 32 f_inside\nF 8c010300 32 f_none\n"
C = """typedef struct { int w[4]; } Stk4;
int f_below(int a4, Stk4 s, float f4)
{
    *(float *)(((int)&s + -4)) = f4;
    return s.w[0];
}
int f_past(int a4, Stk4 s)
{
    s.w[4] = a4;
    *(int *)(((int)&s + 20)) = a4;
    return 0;
}
int f_inside(Stk4 s)
{
    return s.w[0] + s.w[1] + s.w[2] + s.w[3] + *(int *)(((int)&s + 12));
}
int f_none(int a4)
{
    int s[2];
    s[1] = a4;
    return s[1];
}
"""
NAMES = ('f_below', 'f_past', 'f_inside', 'f_none')


def run(repo, *args):
    r = subprocess.run([sys.executable, TOOL] + list(args), cwd=repo, capture_output=True, text=True, timeout=120)
    return r.stdout + r.stderr


def main():
    repo = tempfile.mkdtemp(prefix='consistency_args_')
    try:
        for d in ('src', 'state', 'tests/gen_a'):
            os.makedirs(os.path.join(repo, d))
        open(os.path.join(repo, 'functions.txt'), 'w').write(FUNCTIONS)
        open(os.path.join(repo, 'src', 'gen_a.c'), 'w').write(C)
        open(os.path.join(repo, 'tests', 'equivalent.txt'), 'w').write(''.join(n + '\n' for n in NAMES))
        for n in NAMES:
            open(os.path.join(repo, 'tests', 'gen_a', n + '.json'), 'w').write('{}')
        out = run(repo)
        line = next((l for l in out.splitlines() if l.startswith('args outside')), '')
        assert 'f_below' in line and 'f_past' in line, 'C addressing its stack arguments outside them is not reported:\n' + out
        assert 'f_inside' not in line and 'f_none' not in line, 'a function inside its arguments is reported:\n' + out
        run(repo, '--fix')
        text = open(os.path.join(repo, 'src', 'gen_a.c')).read()
        assert 'int f_below' not in text and 'int f_past' not in text, '--fix leaves C that addresses its arguments outside them'
        assert 'int f_inside' in text and 'int f_none' in text, '--fix removes a function it should keep'
        for n in ('f_below', 'f_past'):
            assert not os.path.exists(os.path.join(repo, 'tests', 'gen_a', n + '.json')), '--fix leaves the cases of ' + n
        assert open(os.path.join(repo, 'tests', 'equivalent.txt')).read().split() == ['f_inside', 'f_none'], '--fix leaves a proof in tests/equivalent.txt'
        assert 'consistent' in run(repo).splitlines()[-1], 'a second run is not consistent'
        print('[consistency_args] ok: C that addresses its stack arguments below or past them is reported and dropped with its cases and proof')
    finally:
        shutil.rmtree(repo, ignore_errors=True)


main()
