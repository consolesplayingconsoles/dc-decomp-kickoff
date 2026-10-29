#!/usr/bin/env python3
"""gen_drv.sign_idiom writes the reader's three-way sign of a float, an if tree
    t = 1; if (X > 0.0f) {} else { t8 = 0; if (0.0f > X) { t8 = 0xFFFFFFFF; } t = t8; }
as one expression `t = (X > 0.0f) - (0.0f > X);`. SHC allocates registers inside one basic block, so the one expression compiles to a
straight run instead of a function whose every value lives in the stack frame (Virtua Tennis cpuSglAimAddLv21: 8,472 bytes down to 4,000).
X is a variable, a difference `(a - b)` or a read of memory `(*(float *)((a8 + 0x3C)))`. The two forms must agree on every value, NaN, -0.0
and the infinities included. No game data, no compiler. Stdlib only.

    check.py      lifts sign_idiom from gen_drv.py (that module needs a repo):
                    forms      each operand kind is rewritten, the helper temporary is dropped from the declarations
                    values     tree and expression give the same result for 0, -0.0, +-1, +-inf, nan and a tiny and a huge value
                    stuck      a tree whose two operands differ, and one with another statement inside, are left as they were
"""
import ast
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '5-generated', 'gen_equiv', 'gen_drv.py')


def lift():
    text = open(SRC, encoding='utf-8').read()
    tree = ast.parse(text)
    ns = {'re': re}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', '') == '_SIGN' for t in node.targets):
            exec(compile(ast.Module(body=[node], type_ignores=[]), SRC, 'exec'), ns)
        if isinstance(node, ast.FunctionDef) and node.name == 'sign_idiom':
            exec(compile(ast.Module(body=[node], type_ignores=[]), SRC, 'exec'), ns)
    return ns['sign_idiom']


def tree(x, t='t1', h='t2', ind='    '):
    return ['%s%s = 0x1;' % (ind, t), '%sif (%s > 0.0f) {' % (ind, x), '%s} else {' % ind, '%s    %s = 0x0;' % (ind, h),
            '%s    if (0.0f > %s) {' % (ind, x), '%s        %s = 0xFFFFFFFF;' % (ind, h), '%s    }' % ind, '%s    %s = %s;' % (ind, t, h), '%s}' % ind]


def main():
    sign_idiom = lift()
    bad = []
    for kind, x in (('variable', 'u7'), ('difference', '(u3 - u2)'), ('memory', '(*(float *)((a8 + 0x3C)))'),
                    ('memory sum', '(*(float *)(((a4 + 0xB00) + 0x4)))')):
        body = ['    a = 5;'] + tree(x) + ['    b = t1;']
        decls = ['int t1;', 'int t2;', 'float u7;']
        out = sign_idiom(list(body), decls)
        want = '    t1 = (%s > 0.0f) - (0.0f > %s);' % (x, x)
        if want not in out or len(out) != 3:
            bad.append('forms: %s operand: %s' % (kind, out))
        if 'int t2;' in decls:
            bad.append('forms: %s operand: the helper temporary t2 stays declared' % kind)
    # values
    for x in (0.0, -0.0, 1.0, -1.0, math.inf, -math.inf, math.nan, 1e-45, 3e38, -3e38):
        t = 1
        if not x > 0.0:
            h = 0
            if 0.0 > x:
                h = -1
            t = h
        e = (x > 0.0) - (0.0 > x)
        if t != e:
            bad.append('values: %r gives %d as a tree and %d as an expression' % (x, t, e))
    # stuck
    other = tree('u7')
    other[4] = '    if (0.0f > u8) {'
    if sign_idiom(list(other), ['int t1;', 'int t2;']) != other:
        bad.append('stuck: a tree with two different operands was rewritten')
    extra = tree('u7')
    extra.insert(3, '        g(1);')
    if sign_idiom(list(extra), ['int t1;', 'int t2;']) != extra:
        bad.append('stuck: a tree with another statement inside was rewritten')
    if bad:
        sys.exit('[ERROR] signidiom check failed:\n' + '\n'.join(bad))
    print('[signidiom] ok: variable, difference and memory operands become one expression; tree and expression agree on 0, -0.0, +-1, +-inf, nan; other trees stay')


if __name__ == '__main__':
    main()
