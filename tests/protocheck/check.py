#!/usr/bin/env python3
"""A call that passes fewer stack words than its callee takes (scripts/tools/8-build/protocheck.py). No game data, no compiler. Stdlib only.

    check.py      a temp repo with src/def.c (the callee's definition), src/short.c and src/full.c:
                    short     a file that prototypes `g(int, float)` for the definition `g(int a4, Stk3 p, float f4)` and calls it
                              directly is reported with 0 words against 3 (Virtua Tennis selPanelDraw: called without its position)
                    full      a file that prototypes all of it is not reported
                    cast      a call through a function-pointer cast is not looked at
                    variadic  a definition with `...` is left alone
                    ints      five integer parameters take one stack word, so a prototype of four is short by one
                  --reads (the registers the original reads against the registers a definition declares; the reads are given, no game data):
                    passed on  cpuDblThinkAll-like `(float, float, float)` against reads r6 r7 fr5 fr6 fr7 is reported for r6, r7 and fr7
                    exact      a definition that declares every register read, a structure in the list (stack) and a function with no reads are not
                    unknown    a function whose reads are not known (None) and a variadic definition are left alone
                    gap        reading r6 with one integer parameter reports r6 (and not r5, which is not read)
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))

DEF_C = ("typedef struct { int w[3]; } Stk3;\nint g(int a4, Stk3 p, float f4)\n{\n    return a4;\n}\n\n"
         "int five(int a4, int a5, int a6, int a7, int a8)\n{\n    return a8;\n}\n\n"
         "int va(int a4, ...)\n{\n    return a4;\n}\n")
SHORT_C = ("int g(int, float);\nint five(int, int, int, int);\nint va(int);\nvoid h(void)\n{\n    g(1, 2.0f);\n    five(1, 2, 3, 4);\n    va(1);\n}\n")
FULL_C = ("typedef struct { int w[3]; } Stk3;\nint g(int, Stk3, float);\nint five(int, int, int, int, int);\nvoid k(void)\n{\n"
          "    g(1, *(Stk3 *)0, 2.0f);\n    five(1, 2, 3, 4, 5);\n}\n")
CAST_C = ("int g(int, float);\nvoid c(void)\n{\n    ((int (*)(int, Stk3, float))(g))(1, *(Stk3 *)0, 2.0f);\n}\n")


READS_C = ("typedef struct { int w[3]; } Stk3;\n"
           "int thinkAll(float f4, float f5, float f6)\n{\n    return 0;\n}\n\n"
           "int exact(int a4, int a5, float f4, float f5)\n{\n    return a4;\n}\n\n"
           "int structy(int a4, Stk3 p, float f4)\n{\n    return a4;\n}\n\n"
           "int quiet(void)\n{\n    return 0;\n}\n\n"
           "int unknown(int a4)\n{\n    return a4;\n}\n\n"
           "int va(int a4, ...)\n{\n    return a4;\n}\n\n"
           "int gap(int a4)\n{\n    return a4;\n}\n")
READS = {'thinkAll': frozenset(['r6', 'r7', 'fr5', 'fr6', 'fr7']), 'exact': frozenset(['r4', 'r5', 'fr4', 'fr5']),
         'structy': frozenset(['r4', 'fr4']), 'quiet': frozenset(), 'unknown': None, 'va': frozenset(['r4', 'r7']), 'gap': frozenset(['r4', 'r6'])}


def reads_check(tmp):
    os.makedirs(os.path.join(tmp, 'src'), exist_ok=True)
    open(os.path.join(tmp, 'src', 'reads.c'), 'w').write(READS_C)
    script = ("import sys; sys.path.insert(0, 'tools'); import toolpath; sys.path.insert(0, 'tools/8-build'); import protocheck\n"
              "R = %r\nfor n, f, miss, pl in sorted(protocheck.scan_reads(reads_of=R.get)):\n    print(n, ' '.join(miss))\n" % READS)
    out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout
    got = sorted(out.strip().split('\n')) if out.strip() else []
    want = ['gap r6', 'thinkAll r6 r7 fr7']
    if got != want:
        sys.exit('[ERROR] protocheck --reads check failed: got %s, want %s' % (got, want))


def main():
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        os.makedirs(os.path.join(tmp, 'src'))
        for n, t in (('def', DEF_C), ('short', SHORT_C), ('full', FULL_C), ('cast', CAST_C)):
            open(os.path.join(tmp, 'src', n + '.c'), 'w').write(t)
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath; sys.path.insert(0, 'tools/8-build'); import protocheck\n"
                  "for n, f, calls, pw, dw in sorted(protocheck.scan()):\n    print(n, f, calls, pw, dw)\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout
        got = sorted(out.strip().split('\n')) if out.strip() else []
        want = ['five src/short.c 1 0 1', 'g src/short.c 1 0 3']
        if got != want:
            sys.exit('[ERROR] protocheck check failed: got %s, want %s' % (got, want))
        reads_check(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('[protocheck] ok: a short prototype that is called is reported, a full one, a cast call and a variadic definition are not; --reads reports the registers a definition leaves out')


if __name__ == '__main__':
    main()
