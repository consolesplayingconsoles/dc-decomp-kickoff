#!/usr/bin/env python3
"""The generator's text for one function written into its file in place of the old one (scripts/tools/5-generated/gen_equiv/regenone.py).
splice() only: the text of the generator is given, nothing is generated. No game data, no compiler. Stdlib only.

    check.py      a temp repo with src/d.c (old, keep) and src/e.c (a prototype of `other`, a definition of `local`):
                    replace   old's definition becomes the new text; keep, next to it, is byte for byte what it was
                    returns   the file written is returned; a name no file defines gives None and no file changes
                    typedef   the new text's Stk3 is declared once, the file's own Stk2 stays
                    proto     a callee the file neither declares nor defines gets a prototype after the last typedef
                    protofix  a prototype the file already has for a callee takes the new signature, once
                    defined   a callee the file defines is given no prototype
                    self      the function itself is given no prototype
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))

D_C = "typedef struct { int w[2]; } Stk2;\n\nint old(int a4)\n{\n    return a4;\n}\n\nint keep(int a4)\n{\n    return a4 + 1;\n}\n"
E_C = ("typedef struct { int w[3]; } Stk3;\nint other(int);\n\nint local(int a4)\n{\n    return a4;\n}\n\n"
       "int old(int a4)\n{\n    return other(a4) + local(a4);\n}\n")
NEW = "typedef struct { int w[3]; } Stk3;\nint old(int a4, Stk3 s)\n{\n    return s.w[2];\n}\n"


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        os.makedirs(os.path.join(tmp, 'src'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(b'\x0b\x00\x09\x00')       # importing the generator reads the original
        open(os.path.join(tmp, 'BASE'), 'w').write('0C010000\n')
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F 0c010000 4 old\n')
        open(os.path.join(tmp, 'src', 'd.c'), 'w').write(D_C)
        script = ("import sys; sys.path[:0] = ['tools', 'tools/5-generated/gen_equiv']; import toolpath, regenone\n"
                  "print('R1', regenone.splice('old', %r, {'other': ['int'], 'keep': ['int'], 'old': ['int', 'Stk3']}))\n"
                  "print('R2', regenone.splice('absent', %r))\n" % (NEW, NEW))
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout
        t = open(os.path.join(tmp, 'src', 'd.c')).read()
        if 'R1 src/d.c' not in out or 'R2 None' not in out:
            bad.append('returns: ' + out[-400:])
        if 'int old(int a4, Stk3 s)\n{\n    return s.w[2];\n}\n' not in t or 'return a4;' in t:
            bad.append('replace: old is not the new text:\n' + t)
        if 'int keep(int a4)\n{\n    return a4 + 1;\n}\n' not in t:
            bad.append('replace: keep changed:\n' + t)
        if t.count('typedef struct { int w[3]; } Stk3;') != 1 or 'typedef struct { int w[2]; } Stk2;' not in t:
            bad.append('typedef: Stk3 not declared once or Stk2 lost:\n' + t)
        if 'int other(int);' not in t or t.index('int other(int);') < t.index('typedef struct { int w[2]; } Stk2;'):
            bad.append('proto: other has no prototype after the typedefs:\n' + t)
        if 'int keep(int);' in t:
            bad.append('defined: keep is defined in the file and was given a prototype:\n' + t)
        if 'int old(int, Stk3);' in t:
            bad.append('self: old was given a prototype:\n' + t)
        open(os.path.join(tmp, 'src', 'e.c'), 'w').write(E_C)
        os.remove(os.path.join(tmp, 'src', 'd.c'))
        script = ("import sys; sys.path[:0] = ['tools', 'tools/5-generated/gen_equiv']; import toolpath, regenone\n"
                  "for _ in range(2): regenone.splice('old', %r, {'other': ['int', 'int'], 'local': ['int']})\n" % NEW)
        subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
        e = open(os.path.join(tmp, 'src', 'e.c')).read()
        if e.count('int other(int, int);') != 1 or 'int other(int);' in e:
            bad.append('protofix: other\'s prototype is not the new signature, once:\n' + e)
        if 'int local(int);' in e:
            bad.append('defined: local is defined in the file and was given a prototype:\n' + e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] regenone check failed:\n' + '\n'.join(bad))
    print('[regenone] ok: only the named function is replaced, its callees get prototypes where the file has none, the typedefs are not doubled')


if __name__ == '__main__':
    main()
