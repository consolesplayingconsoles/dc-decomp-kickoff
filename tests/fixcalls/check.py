#!/usr/bin/env python3
"""The call sites of a function that takes its stack words as a structure or as ints (scripts/tools/5-generated/gen_equiv/fixcalls.py).
No game data, no compiler. Stdlib only.

    check.py      a temp repo with src/a.c and src/b.c, the callee's definition in src/def.c:
                    struct    `f(a, b, 1.0f);` after a block copy of three words: the argument `*(Stk3 *)(SRC)` goes in after the second,
                              the copy is gone, and the prototype in the file takes `Stk3` there
                    ints      the same with name:3:1:i: three int arguments `*(int *)(SRC + 0)`, `+ 4`, `+ 8`
                    only      @file.json limits the change to the files named for the function: b.c is left alone
                    protos    --protos gives a file's prototype the definition's parameter types (the names dropped)
                    again     a call that already passes the structure is not changed twice
                    store     a store of the pointer argument at stk + 8, then the call: the structure is `*(Stk3 *)((int)stk + 12)`
                    built     a `*(Stk3 *)((int)stk + 16) = vecMake(...)` before the call: the structure built there
                    return    `return f(...)` takes the argument, and its block copy is gone
                    cast      a call through `((int (*)(int, int, float))(f))(...)` takes it in the argument list and in the cast's type list
                    prev      with --prev a call with no setup of its own takes the structure the call just before it was given; without
                              --prev it is listed and left alone
                    none      a call with no setup at all is left alone and counted
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))

A_C = ("typedef struct { int w[3]; } Stk3;\nint f(int, int, float);\n\nvoid caller(int a4)\n{\n    int stk[8];\n"
       "    { struct mv3 { int w[3]; }; *(struct mv3 *)(((int)stk + 4)) = *(struct mv3 *)((a4 + 0x10)); }\n    f(a4, 2, 1.0f);\n}\n")
B_C = A_C.replace('caller', 'other')
X_C = """typedef struct { int w[3]; } Stk3;
int f(int, int, float);

void store(int a4, int a5)
{
    int stk[12];

    *(int *)((int)stk + 8) = a5;
    f(a4, a5, 1.0f);
}

void built(int a4)
{
    int stk[12];

    *(Stk3 *)((int)stk + 16) = vecMake(1.0f, 2.0f, 3.0f);
    f(a4, 2, 1.0f);
}

void prev(int a4)
{
    int stk[12];

    f(a4, 1, *(Stk3 *)(a4 + 8), 1.0f);
    f(a4, 2, 1.0f);
}

int ret(int a4)
{
    int stk[12];

    { struct mv3 { int w[3]; }; *(struct mv3 *)(((int)stk + 4)) = *(struct mv3 *)((a4 + 0x20)); }
    return f(a4, 3, 1.0f);
}

void cast(int a4)
{
    int stk[12];

    { struct mv3 { int w[3]; }; *(struct mv3 *)(((int)stk + 4)) = *(struct mv3 *)((a4 + 0x30)); }
    ((int (*)(int, int, float))(f))(a4, 4, 1.0f);
}

void none(int a4)
{
    f(a4, 5, 1.0f);
}
"""
DEF_C = "typedef struct { int w[3]; } Stk3;\nint f(int a4, int a5, Stk3 p, float f4)\n{\n    return a4;\n}\n"


def run(tmp, *args):
    return subprocess.run([sys.executable, 'tools/5-generated/gen_equiv/fixcalls.py'] + list(args), cwd=tmp, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, universal_newlines=True).stdout


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        os.makedirs(os.path.join(tmp, 'src'))
        w = lambda n, t: open(os.path.join(tmp, 'src', n), 'w').write(t)
        r = lambda n: open(os.path.join(tmp, 'src', n)).read()
        w('a.c', A_C); w('b.c', B_C); w('def.c', DEF_C)
        json.dump({'f': ['src/a.c']}, open(os.path.join(tmp, 'only.json'), 'w'))
        out = run(tmp, '--fix', '@only.json', 'f:3:1')
        a, b = r('a.c'), r('b.c')
        if 'f(a4, 2, *(Stk3 *)((a4 + 0x10)), 1.0f);' not in a:
            bad.append('struct: the argument is not in:\n' + a + out)
        if 'struct mv3' in a:
            bad.append('struct: the block copy is still there:\n' + a)
        if b != B_C:
            bad.append('only: b.c changed:\n' + b)
        run(tmp, '--fix', '@only.json', 'f:3:1')
        if r('a.c').count('*(Stk3 *)') != 1:
            bad.append('again: changed twice:\n' + r('a.c'))
        run(tmp, '--protos', '@only.json', 'f')
        if 'int f(int, int, Stk3, float);' not in r('a.c') or 'int f(int, int, float);' not in r('b.c'):
            bad.append('protos:\n' + r('a.c') + r('b.c'))
        w('a.c', A_C)
        run(tmp, '--fix', '@only.json', 'f:3:1:i')
        a = r('a.c')
        for need in ('*(int *)(((a4 + 0x10)) + 0)', '*(int *)(((a4 + 0x10)) + 4)', '*(int *)(((a4 + 0x10)) + 8)'):
            if need not in a:
                bad.append('ints lacks %s:\n%s' % (need, a))
        w('a.c', X_C)
        os.remove(os.path.join(tmp, 'src', 'b.c'))                  # its call was left alone by `only`; here every call in the repo counts
        out = run(tmp, '--fix', 'f:3:1')
        x = r('a.c')
        for need in ('f(a4, a5, *(Stk3 *)((int)stk + 12), 1.0f);', 'f(a4, 2, *(Stk3 *)((int)stk + 16), 1.0f);', 'return f(a4, 3, *(Stk3 *)((a4 + 0x20)), 1.0f);',
                     '((int (*)(int, int, Stk3, float))(f))(a4, 4, *(Stk3 *)((a4 + 0x30)), 1.0f);'):
            if need not in x:
                bad.append('setups lacks %s:\n%s%s' % (need, x, out))
        if 'struct mv3' in x:
            bad.append('return/cast: a block copy is still there:\n' + x)
        if 'f(a4, 2, 1.0f);\n}\n\nint ret' not in x or 'f(a4, 5, 1.0f);' not in x:
            bad.append('prev/none: a call without a setup changed without --prev:\n' + x)
        if 'fixcalls: 4 call(s) changed, 2 left alone' not in out:
            bad.append('counts: want 4 changed and 2 left alone:\n' + out)
        out = run(tmp, '--prev', '--fix', 'f:3:1')
        x = r('a.c')
        if 'f(a4, 2, *(Stk3 *)(a4 + 8), 1.0f);' not in x or 'f(a4, 5, 1.0f);' not in x or 'fixcalls: 1 call(s) changed, 1 left alone' not in out:
            bad.append('prev: --prev gives the second call the first one\'s structure and leaves `none`:\n' + x + out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] fixcalls check failed:\n' + '\n'.join(bad))
    print('[fixcalls] ok: the stack words are passed as a structure or as ints, only where named, once, and the prototypes follow')


if __name__ == '__main__':
    main()
