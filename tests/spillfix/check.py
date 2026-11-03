#!/usr/bin/env python3
"""A generated function that spills its stack parameters into the frame and then reads the words after them, which nothing stored
(scripts/tools/5-generated/gen_equiv/spillfix.py). No game data, no compiler. Stdlib only.

    check.py      a temp repo with src/a.c, run as the tool is run (report, then --fix):
                    report    m spills a8 and a9 into stk[10], stk[11] and reads stk + 48 and stk + 52 (words 2 and 3 after the entry):
                              reported with 2 declared and words [2, 3] read
                    fix       --fix gives m one structure `Stk4 s` in place of a8 and a9, four spills stk[10..13] = s.w[0..3] where the two
                              were, the typedef and the prototype; the float parameter stays after it
                    covered   n reads only the words it spilled: not reported
                    stored    k stores the third word itself before reading it: not reported
                    only      naming a function on the command line leaves the others alone
                    again     a second --fix changes nothing
                    single    a read written `*(int *)((int)stk + 48)`, the form the generator writes, is seen as a read like the
                              three-parenthesis form
                    blockmove the block move of the arguments (`*(struct mv3 *)(...) = *(struct mv3 *)(((int)stk + 40))`) reads the words after the
                              declared one: reported
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))

A_C = """int m(int a4, int a5, int a6, int a7, int a8, int a9, float f4);
int n(int a4, int a5, int a6, int a7, int a8, int a9);
int k(int a4, int a5, int a6, int a7, int a8, int a9);
int s1(int a4, int a5, int a6, int a7, int a8);
int bm(int a4, int a5, int a6, int a7, int a8);

int m(int a4, int a5, int a6, int a7, int a8, int a9, float f4)
{
    int stk[20];

    stk[10] = a8;
    stk[11] = a9;
    return *(int *)(((int)stk + 48)) + *(int *)(((int)stk + 52));
}

int n(int a4, int a5, int a6, int a7, int a8, int a9)
{
    int stk[20];

    stk[10] = a8;
    stk[11] = a9;
    return *(int *)(((int)stk + 40)) + *(int *)(((int)stk + 44));
}

int k(int a4, int a5, int a6, int a7, int a8, int a9)
{
    int stk[20];

    stk[10] = a8;
    stk[11] = a9;
    *(int *)(((int)stk + 48)) = 5;
    return *(int *)(((int)stk + 48));
}

int s1(int a4, int a5, int a6, int a7, int a8)
{
    int stk[20];

    stk[10] = a8;
    return *(int *)((int)stk + 44) + *(int *)((int)stk + 48);
}

int bm(int a4, int a5, int a6, int a7, int a8)
{
    int stk[20];

    stk[10] = a8;
    { struct mv3 { int w[3]; }; *(struct mv3 *)(((int)stk + 60)) = *(struct mv3 *)(((int)stk + 40)); }
    return *(int *)((int)stk + 64);
}
"""


def run(tmp, *args):
    return subprocess.run([sys.executable, 'tools/5-generated/gen_equiv/spillfix.py'] + list(args), cwd=tmp, stdout=subprocess.PIPE,
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
        if 'm: declares 2 stack word(s), reads word(s) [2, 3]' not in rep:
            bad.append('report: m is not reported:\n' + rep)
        if ': n:' in rep:
            bad.append('covered: n reads only what it spilled and must not be reported:\n' + rep)
        if ': k:' in rep:
            bad.append('stored: k stores the word it reads and must not be reported:\n' + rep)
        if 's1: declares 1 stack word(s), reads word(s) [1, 2]' not in rep:
            bad.append('single: the single-parenthesis reads are not seen:\n' + rep)
        if 'bm: declares 1 stack word(s), reads word(s) [1, 2]' not in rep:
            bad.append('blockmove: the block move of the arguments is not seen:\n' + rep)
        run(tmp, '--fix', 'n')
        if open(path).read() != A_C:
            bad.append('only: --fix n changed the file though n has nothing to fix')
        run(tmp, '--fix', 'm')
        t = open(path).read()
        if 'int m(int a4, int a5, int a6, int a7, Stk4 s, float f4)\n{' not in t or 'int m(int a4, int a5, int a6, int a7, Stk4 s, float f4);' not in t:
            bad.append('fix: signature and prototype:\n' + t)
        if '    stk[10] = s.w[0];\n    stk[11] = s.w[1];\n    stk[12] = s.w[2];\n    stk[13] = s.w[3];\n' not in t:
            bad.append('fix: the four spills:\n' + t)
        i_, j_ = t.find('int m(int a4, int a5, int a6, int a7, Stk4 s, float f4)\n{'), t.find('int n(int a4, int a5, int a6, int a7, int a8, int a9)\n{')
        mt = t[max(i_, 0):j_ if j_ > i_ else len(t)]
        if 'a8' in mt or 'a9' in mt:
            bad.append('fix: a8 or a9 is still in m:\n' + mt)
        if 'typedef struct { int w[4]; } Stk4;' not in t:
            bad.append('fix: no typedef of Stk4:\n' + t)
        if 'int s1(int a4, int a5, int a6, int a7, int a8)\n{' not in t or 'int bm(int a4, int a5, int a6, int a7, int a8)\n{' not in t:
            bad.append('only: s1 or bm changed:\n' + t)
        if 'int n(int a4, int a5, int a6, int a7, int a8, int a9)\n{' not in t or 'int k(int a4, int a5, int a6, int a7, int a8, int a9)\n{' not in t:
            bad.append('only: n or k changed:\n' + t)
        run(tmp, '--fix', 'm')
        if open(path).read() != t:
            bad.append('again: a second --fix changed the file')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] spillfix check failed:\n' + '\n'.join(bad))
    print('[spillfix] ok: spilled stack words that are read past what was declared become one structure parameter, covered and stored ones are left')


if __name__ == '__main__':
    main()
