#!/usr/bin/env python3
"""A generated function that reads the words its caller pushed, through offsets past its own frame array, gets them as parameters
(scripts/tools/5-generated/gen_equiv/stackparams.py). No game data, no compiler. Stdlib only.

    check.py      a temp repo with src/a.c, run as the tool is run (report, then --fix):
                    report    f reads `stk + 16` and `stk + 20` with a 16-byte frame: reported with both words; g reads inside its frame: not
                    two       two words become one structure `Stk2 s` after the register parameters (a4-a7), read as s.w[0] and s.w[1],
                              the typedef is added, the prototype follows
                    one       a single word becomes an int parameter (a8), not a structure
                    float     a word read as a float is read as `*(float *)&s.w[0]`
                    inside    g, which reads only inside its frame, is not touched
                    skips     a frame address built from a parameter, and a parameter that is not a plain int or float, are reported as skipped and the
                              function is left as it was
                    only      naming a function on the command line converts that one alone
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))

A_C = """int f(int a4);
int g(int a4);
int one(int a4);
int flt(int a4);
int var(int a4);
int strct(int a4, Stk1 s);

int f(int a4)
{
    int stk[4];

    stk[0] = a4;
    return *(int *)((int)stk + 16) + *(int *)((int)stk + 20);
}

int g(int a4)
{
    int stk[4];

    stk[0] = a4;
    return *(int *)((int)stk + 8);
}

int one(int a4)
{
    int stk[4];

    stk[0] = a4;
    return *(int *)((int)stk + 16);
}

int flt(int a4)
{
    int stk[4];
    float u0;

    u0 = *(float *)((int)stk + 16);
    return *(int *)((int)stk + 20) + a4;
}

int var(int a4)
{
    int stk[4];

    return *(int *)((int)stk + a4);
}

int strct(int a4, Stk1 s)
{
    int stk[4];

    return *(int *)((int)stk + 16);
}
"""


def run(tmp, *args):
    return subprocess.run([sys.executable, 'tools/5-generated/gen_equiv/stackparams.py'] + list(args), cwd=tmp, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, universal_newlines=True).stdout


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        os.makedirs(os.path.join(tmp, 'src'))
        path = os.path.join(tmp, 'src', 'a.c')
        open(path, 'w').write(A_C)
        rep = run(tmp)
        if open(path).read() != A_C:
            bad.append('report: the file changed without --fix')
        if 'f: frame 16 bytes, stack words 0 (int), 1 (int)' not in rep:
            bad.append('report: f is not reported with its two words:\n' + rep)
        if ': g:' in rep:
            bad.append('report: g reads inside its frame and must not be reported:\n' + rep)
        if 'var: skipped: an address that cannot be read' not in rep:
            bad.append('skips: frame address from a parameter:\n' + rep)
        if 'strct: skipped: a parameter that is not a plain int or float' not in rep:
            bad.append('skips: structure parameter:\n' + rep)
        out = run(tmp, '--fix', 'f')
        t = open(path).read()
        if 'int f(int a4, int a5, int a6, int a7, Stk2 s)\n{' not in t or 'int f(int a4, int a5, int a6, int a7, Stk2 s);' not in t:
            bad.append('two: signature and prototype:\n' + t + out)
        if 'return s.w[0] + s.w[1];' not in t:
            bad.append('two: the reads are not s.w[0] and s.w[1]:\n' + t)
        if 'typedef struct { int w[2]; } Stk2;' not in t:
            bad.append('two: no typedef of Stk2:\n' + t)
        if 'int one(int a4)\n{' not in t:
            bad.append('only: one was converted though only f was named:\n' + t)
        run(tmp, '--fix')
        t = open(path).read()
        if 'int one(int a4, int a5, int a6, int a7, int a8)\n{' not in t or 'return a8;' not in t:
            bad.append('one: a single word is an int parameter a8:\n' + t)
        if '(*(float *)&s.w[0])' not in t:
            bad.append('float: a float read is not (*(float *)&s.w[0]):\n' + t)
        if 'int g(int a4)\n{\n    int stk[4];\n\n    stk[0] = a4;\n    return *(int *)((int)stk + 8);\n}' not in t:
            bad.append('inside: g changed:\n' + t)
        if 'int var(int a4)\n{' not in t or 'int strct(int a4, Stk1 s)\n{' not in t:
            bad.append('skips: a skipped function changed:\n' + t)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] stackparams check failed:\n' + '\n'.join(bad))
    print('[stackparams] ok: words past the frame become parameters (a structure for two or more, an int for one), the rest is left alone')


if __name__ == '__main__':
    main()
