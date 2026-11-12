#!/usr/bin/env python3
"""Generated C that calls one of the compiler's register helpers by name (scripts/tools/consistency.py). The helpers take their operands in
r0-r2, so a C call runs on whatever those registers hold. Zombie Revenge: 36 functions were generated while _quick_odd_mvn and _divls had
FUN_ names and were renamed later; FUN_0c07f340's 12-byte copy jumped into a texture through the helper's `braf r0` as the player took
control, and its proof had passed because no case reached the call. No game data, no compiler. Stdlib only.

    check.py      a temp repo: functions.txt with four functions, src/gen_a.c defining them, cases and tests/equivalent.txt for each:
                    f_mvn    calls _quick_odd_mvn as a statement:             reported as `helper call`
                    f_div    calls _divls through a cast:                     reported
                    f_copy   a struct copy (what the generator writes now):   not reported
                    f_named  calls a function whose name only contains one:   not reported
                  --fix drops f_mvn and f_div with their cases and their lines in tests/equivalent.txt and keeps the others;
                  a second run reports consistent
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', 'consistency.py')

FUNCTIONS = "F 8c010000 32 f_mvn\nF 8c010100 32 f_div\nF 8c010200 32 f_copy\nF 8c010300 32 f_named\n"
C = """int _quick_odd_mvn(int, int, int, int, float, float);
int _divls(void);
int my_divls(int);
int f_mvn(int a4)
{
    int R4;
    R4 = a4;
    _quick_odd_mvn(R4, 0, 0, 0, 0.0f, 0.0f);
    return R4;
}
int f_div(int a4)
{
    return ((int (*)(void))(_divls))();
}
int f_copy(int a4)
{
    { struct mv3 { int w[3]; }; *(struct mv3 *)((0x284 + a4)) = *(struct mv3 *)((0x338 + a4)); }
    return 0;
}
int f_named(int a4)
{
    return my_divls(a4);
}
"""
NAMES = ('f_mvn', 'f_div', 'f_copy', 'f_named')


def run(repo, *args):
    r = subprocess.run([sys.executable, TOOL] + list(args), cwd=repo, capture_output=True, text=True, timeout=120)
    return r.stdout + r.stderr


def main():
    repo = tempfile.mkdtemp(prefix='consistency_helper_')
    try:
        for d in ('src', 'state', 'tests/gen_a'):
            os.makedirs(os.path.join(repo, d))
        open(os.path.join(repo, 'functions.txt'), 'w').write(FUNCTIONS)
        open(os.path.join(repo, 'src', 'gen_a.c'), 'w').write(C)
        open(os.path.join(repo, 'tests', 'equivalent.txt'), 'w').write(''.join(n + '\n' for n in NAMES))
        for n in NAMES:
            open(os.path.join(repo, 'tests', 'gen_a', n + '.json'), 'w').write('{}')
        out = run(repo)
        line = next((l for l in out.splitlines() if l.startswith('helper call')), '')
        assert 'f_mvn' in line and 'f_div' in line, 'a C call to a register helper is not reported:\n' + out
        assert 'f_copy' not in line and 'f_named' not in line, 'a function with no helper call is reported:\n' + out
        run(repo, '--fix')
        text = open(os.path.join(repo, 'src', 'gen_a.c')).read()
        assert 'int f_mvn' not in text and 'int f_div' not in text, '--fix leaves a helper call in src/gen_a.c'
        assert 'int f_copy' in text and 'int f_named' in text, '--fix removes a function it should keep'
        for n in ('f_mvn', 'f_div'):
            assert not os.path.exists(os.path.join(repo, 'tests', 'gen_a', n + '.json')), '--fix leaves the cases of ' + n
        assert open(os.path.join(repo, 'tests', 'equivalent.txt')).read().split() == ['f_copy', 'f_named'], '--fix leaves a proof in tests/equivalent.txt'
        assert 'consistent' in run(repo).splitlines()[-1], 'a second run is not consistent'
        print('[consistency_helper] ok: C that calls a register helper by name is reported, dropped with its cases and proof; the others stay')
    finally:
        shutil.rmtree(repo, ignore_errors=True)


main()
