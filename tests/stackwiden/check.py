#!/usr/bin/env python3
"""A function that takes fewer stack words than its original reads gets one structure parameter of the right size
(scripts/tools/5-generated/gen_equiv/stackwiden.py). No game data, no compiler. Stdlib only.

    check.py      stackwiden.rewrite on small functions:
                    intform   `int f(int a4, int a5, int a6, int a7, int a8)` with `stk[10] = a8;`: the parameters become
                              `int a4, int a5, int a6, int a7, Stk3 p`, three spills stk[10..12] = p.w[0..2] before the first statement,
                              the typedef, and the prototype follows
                    structform `int f(Stk1 s, float f4)` with `stk[5] = s.w[0];`: `Stk4 p`, four spills
                    nospill   a function with no spill of a stack word is not rewritten
                    search    main() with a stand-in tools/equiv.py that passes the fuzzed run from K=5 up: it writes K=3, 4, 5 in turn
                              (the default list), stops at 5 with exit 0 and leaves the file at K=5; a named list (6 7) starts there
                    restore   a stand-in that never passes: every K is tried, the file is put back byte for byte, exit 2
                    skip      a function with no spill line: exit 1, the file untouched, equiv.py never run
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))

INTFORM = ("int f(int a4, int a5, int a6, int a7, int a8);\n\nint f(int a4, int a5, int a6, int a7, int a8)\n{\n    int stk[20];\n    float u0;\n\n"
           "    stk[10] = a8;\n    u0 = *(float *)((int)stk + 40);\n    return a4;\n}\n")
STRUCTFORM = ("typedef struct { int w[1]; } Stk1;\nint f(Stk1 s, float f4);\n\nint f(Stk1 s, float f4)\n{\n    int stk[12];\n\n"
              "    stk[5] = s.w[0];\n    return stk[5];\n}\n")
NOSPILL = "int f(int a4)\n{\n    return a4;\n}\n"


STUB = """import os, re, sys
t = open(sys.argv[1]).read()
k = int(re.search(r'Stk(\\d+) p', t).group(1))
open('equiv.log', 'a').write('%d %s\\n' % (k, os.environ.get('STACKFUZZ', 'plain')))
ok = k >= int(os.environ.get('STUB_PASS_FROM', '99')) if os.environ.get('STACKFUZZ') else True
print('%-28s %-11s %s' % ('f', 'EQUIVALENT' if ok else 'DIFFERS', 'stand-in'))      # the last line without -q: one verdict per function
"""


def widen(tmp, src, *extra, env=None):
    open(os.path.join(tmp, 'src.c'), 'w').write(src)
    if os.path.exists(os.path.join(tmp, 'equiv.log')):
        os.remove(os.path.join(tmp, 'equiv.log'))
    r = subprocess.run([sys.executable, 'tools/5-generated/gen_equiv/stackwiden.py', 'src.c', 'f'] + list(extra), cwd=tmp, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, universal_newlines=True, env=dict(os.environ, **(env or {})))
    log = open(os.path.join(tmp, 'equiv.log')).read().split('\n') if os.path.exists(os.path.join(tmp, 'equiv.log')) else []
    return r.returncode, r.stdout, open(os.path.join(tmp, 'src.c')).read(), [x for x in log if x]


def main():
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath; sys.path.insert(0, 'tools/5-generated/gen_equiv'); import stackwiden\n"
                  "a, sa = stackwiden.rewrite(%r, 'f', 3)\nprint('@@A'); print(a); print('@@S', sa)\n"
                  "b, sb = stackwiden.rewrite(%r, 'f', 4)\nprint('@@B'); print(b); print('@@S', sb)\n"
                  "c, sc = stackwiden.rewrite(%r, 'f', 3)\nprint('@@C', c, sc)\n" % (INTFORM, STRUCTFORM, NOSPILL))
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout
        bad = []
        a = out.split('@@A')[1].split('@@S')[0] if '@@A' in out else ''
        b = out.split('@@B')[1].split('@@S')[0] if '@@B' in out else ''
        for need in ('int f(int a4, int a5, int a6, int a7, Stk3 p);', 'int f(int a4, int a5, int a6, int a7, Stk3 p)\n{', 'typedef struct { int w[3]; } Stk3;',
                     '    stk[10] = p.w[0];\n    stk[11] = p.w[1];\n    stk[12] = p.w[2];\n    u0 = '):
            if need not in a:
                bad.append('intform lacks %r:\n%s' % (need, a))
        if 'a8' in a:
            bad.append('intform keeps a8:\n' + a)
        for need in ('int f(Stk4 p, float f4)\n{', 'stk[5] = p.w[0];', 'stk[8] = p.w[3];', 'typedef struct { int w[4]; } Stk4;'):
            if need not in b:
                bad.append('structform lacks %r:\n%s' % (need, b))
        if '@@C None no spill line of a stack word' not in out:
            bad.append('nospill: ' + out[-200:])
        open(os.path.join(tmp, 'tools', 'equiv.py'), 'w').write(STUB)
        rc, out, text, log = widen(tmp, INTFORM, env={'STUB_PASS_FROM': '5'})
        if rc != 0 or 'Stk5 p' not in text or log != ['3 1', '3 plain', '4 1', '4 plain', '5 1', '5 plain']:
            bad.append('search: want exit 0 at K=5 after trying 3, 4, 5; got exit %s, log %s:\n%s%s' % (rc, log, out, text))
        rc, out, text, log = widen(tmp, INTFORM, '6', '7', env={'STUB_PASS_FROM': '5'})
        if rc != 0 or 'Stk6 p' not in text or log != ['6 1', '6 plain']:
            bad.append('search: a named list starts at its first: exit %s, log %s' % (rc, log))
        rc, out, text, log = widen(tmp, INTFORM, env={'STUB_PASS_FROM': '99'})
        if rc != 2 or text != INTFORM or 'no K passed; file restored' not in out or len(log) != 16:
            bad.append('restore: want exit 2, the file as it was and 8 K tried; got exit %s, %d runs:\n%s' % (rc, len(log), text))
        rc, out, text, log = widen(tmp, NOSPILL, env={'STUB_PASS_FROM': '3'})
        if rc != 1 or text != NOSPILL or log:
            bad.append('skip: want exit 1, file untouched, equiv.py not run; got exit %s, log %s' % (rc, log))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] stackwiden check failed:\n' + '\n'.join(bad))
    print('[stackwiden] ok: the stack words become one structure parameter with every spill, the prototype follows, a function without a spill is left')


if __name__ == '__main__':
    main()
