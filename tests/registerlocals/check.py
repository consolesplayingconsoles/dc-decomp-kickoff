#!/usr/bin/env python3
"""gen_drv.register_locals declares the scalar locals of a generated function `register`: SHC then allocates registers far better in the big
functions (Virtua Tennis menuTextMsgPutB 11,220 -> 5,972 bytes, entryGridDrawCursors 7,180 -> 5,636). Arrays, pointers, a variable whose
address is taken and the part dispatcher's NEXT_ stay as they are (a register variable has no address; C rejects `&t1` on one).
No game data, no compiler. Stdlib only.

    check.py      lifts register_locals from gen_drv.py:
                    scalars    int, unsigned int, short, char and float locals gain `register`, indentation and name kept
                    kept       `int stk[69];`, `int *S_ = S_v;`, a name used as `&name`, and NEXT_ are not changed
                    twice      applying it again changes nothing
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '5-generated', 'gen_equiv', 'gen_drv.py')


def lift():
    tree = ast.parse(open(SRC, encoding='utf-8').read())
    ns = {'re': re}
    for node in tree.body:
        ok = (isinstance(node, ast.Assign) and any(getattr(t, 'id', '') == '_LOCAL' for t in node.targets)) or \
             (isinstance(node, ast.FunctionDef) and node.name == 'register_locals')
        if ok:
            exec(compile(ast.Module(body=[node], type_ignores=[]), SRC, 'exec'), ns)
    return ns['register_locals']


def main():
    reg = lift()
    text = '\n'.join(['int f(int a4)', '{', '    int t1;', '    unsigned int t2;', '    short t3;', '    char t4;', '    float u5;', '    int stk[69];',
                       '    int *S_ = S_v;', '    int t6;', '    int NEXT_;', '', '    t1 = a4;', '    g(&t6);', '    return t1;', '}'])
    out = reg(text)
    bad = []
    for want in ('    register int t1;', '    register unsigned int t2;', '    register short t3;', '    register char t4;', '    register float u5;'):
        if want not in out.split('\n'):
            bad.append('scalars: missing %r' % want)
    for keep in ('    int stk[69];', '    int *S_ = S_v;', '    int t6;', '    int NEXT_;', 'int f(int a4)'):
        if keep not in out.split('\n'):
            bad.append('kept: %r changed' % keep)
    if reg(out) != out:
        bad.append('twice: a second application changes the text')
    if bad:
        sys.exit('[ERROR] registerlocals check failed:\n' + '\n'.join(bad))
    print('[registerlocals] ok: scalar locals become register; arrays, pointers, address-taken names and NEXT_ stay; idempotent')


if __name__ == '__main__':
    main()
