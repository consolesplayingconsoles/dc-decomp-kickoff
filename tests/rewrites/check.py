#!/usr/bin/env python3
"""The size rewrites of generated C (scripts/tools/5-generated/gen_equiv/rewrites.py: the generator's last passes and shrink.py's
--passes strategies). No game data, no compiler. Stdlib only.

A field read or written at an offset past the short displacement form is written as a member of a one-field structure.

SHC compiles `*(int *)((a4 + 0x2D4))` with an int base as integer arithmetic: it keeps the offsets in saved registers and adds
them to the base for every access. `((struct o2D4_int *)(a4))->v` compiles as the original's `mov.w #off,r0; mov.l @(r0,Rn)`,
as `p->field` does (Zombie Revenge FUN_0c031e5e: 360 bytes of C to 296; five such accesses, 52 bytes to 32).

    check.py      drop_self_copies on C text:
                    self      a frame slot stored back with its own value goes; another slot or another width stays
                  struct_access on C text:
                    far       an int at 0x2D4 becomes a member, and the declaration is listed
                    near      an int at 0x10 (mov.l @(disp,Rn) reaches it) is left as it is
                    kinds     short past 30, char past 15 and any float offset are members of their own type
                    nested    a base that itself holds a far access is rewritten inside
                    order     the constant first, `(0xC0 + a4)`, and a trailing `+ 0x0` wrapper are the same access
                    volatile  a volatile access is left as it is (the struct's member is not volatile)
                    pointer   a base declared as a pointer or an array is left as it is (its + scales)
                    decls     struct_decls lists each structure once, in a stable order
                  global_base on C text:
                    global    nearby fixed addresses are members off the lowest (offset 0 has no padding); a lone one is left
                    volatile  a volatile global is left as it is
                  narrow_calls on a unit's text:
                    narrow    a callee declared wider than its definition is declared as defined; its calls drop the extra arguments
                    keepcall  a callee with a call whose dropped argument would hold a call is left as it is, declaration and calls
                    types     a declaration whose leading types differ from the definition's is left as it is
                    vararg    a variadic declaration is left as it is
                  drop_dead_frame on C text:
                    dead      stores to stk slots, bare volatile stk reads and the array itself go when nothing else uses stk
                    read      a slot read anywhere: left
                    address   the array's address passed on: left
                    call      a store whose value comes from a call (the call stays, so does the store): left
                    volatile  a store whose value is a volatile read: left
                    twice     a second run changes nothing
                  hoist_builtins on C text:\n                    hoist     three `_builtin_sqrtf(u5)` in one block, u5 not assigned after the first: one `s1 = ...` before the first, the calls read s1\n                    reassigned the argument assigned between the calls: left\n                    loop      a function with for/while/goto/label: left\n                    expr      an argument that is not a plain variable: left\n                    branches  calls only in sibling branches (no block holds all): left\n                    twice     a second run changes nothing\n                  frame_rebase on C text:
                    rebase    `int stk[16]` used from `(int)stk + 4` on: every offset 4 lower, one word less; two functions in one text each by their own lowest offset
                    zero      a first slot already at 0: left
                    index     a function that uses stk[..] or any other form: left
                    odd       an offset that is not a word multiple: left
                    twice     a second run changes nothing
                  merge_copies on C text:
                    merge     `t70 = (t30);` with t30 dead after: t30 becomes t70 and the copy goes
                    goto      a goto, break, continue or label between t30's first use and the copy: left
                    live      t30 still read after the copy: left
                    tA used   t70 read while t30 is live: left
                  chains_to_switch on C text:
                    switch    a != chain of three levels on one variable becomes a switch, arms as cases, the innermost then-block the default
                    switch == the == form, its else-block the next level; no default when nothing is left
                    break     an arm holding a break; is left (it would leave the switch)
                    short     two levels stay as they are
                  narrow_unit: the generator's hook on a whole unit; the line count is unchanged
                  splice on a unit's text:
                    replace   the named function's definition is replaced, the other left as it is
                    decls     the structures it names are declared once, after the head and before the first definition
                    again     a second splice of the same function adds no declaration twice
                    none      a function that names no structure adds no declaration
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))


def load():
    sys.path.insert(0, os.path.join(SKILL, 'scripts', 'tools', '5-generated', 'gen_equiv'))
    sys.path.insert(0, os.path.join(SKILL, 'scripts', 'tools'))
    import toolpath  # noqa: F401
    import rewrites
    return rewrites.struct_access, rewrites.struct_decls


def fn(body, decls='    int t7;\n'):
    return 'int f(int a4, float *p)\n{\n%s\n%s}\n' % (decls, body)


def main():
    sa, sd = load()
    bad = []
    got = sa(fn('    *(unsigned int *)((a4 + 0x2D4)) = 0x1;\n'))
    if '(((struct o2D4_uint *)(a4))->v) = 0x1;' not in got:
        bad.append('far: %s' % got)
    if sd(got) != ['struct o2D4_uint { char p[0x2D4]; unsigned int v; };']:
        bad.append('far decls: %s' % sd(got))
    src = fn('    t7 = *(int *)((a4 + 0x10));\n')
    if sa(src) != src:
        bad.append('near: %s' % sa(src))
    got = sa(fn('    *(short *)((a4 + 0x20)) = *(char *)((a4 + 0x10));\n    t7 = (int)*(float *)((a4 + 0x4));\n'))
    for want in ('((struct o20_short *)(a4))->v', '((struct o10_char *)(a4))->v', '((struct o4_float *)(a4))->v'):
        if want not in got:
            bad.append('kinds: %s missing in %s' % (want, got))
    got = sa(fn('    t7 = *(int *)(((*(int *)((a4 + 0x540))) + 0x4));\n    t7 = *(int *)(((*(int *)((a4 + 0x540))) + 0x80));\n'))
    if '((struct o80_int *)(((((struct o540_int *)(a4))->v))))->v' not in got or '*(int *)((((((struct o540_int *)(a4))->v)) + 0x4))' not in got:
        bad.append('nested: %s' % got)
    got = sa(fn('    *(int *)(((0xC0 + a4) + 0x0)) = 1;\n    t7 = *(float *)(((a4 + 0x34) + 0x0));\n    t7 = *(int *)((0x1C4 + a5));\n'))
    for want in ('(((struct oC0_int *)(a4))->v) = 1;', '(((struct o34_float *)(a4))->v)', '(((struct o1C4_int *)(a5))->v)'):
        if want not in got:
            bad.append('order: %s missing in %s' % (want, got))
    src = fn('    *(volatile int *)((a4 + 0x200));\n')
    if sa(src) != src:
        bad.append('volatile: %s' % sa(src))
    src = fn('    t7 = *(int *)((p + 0x80));\n    t7 = *(int *)((u9 + 0x80));\n', '    int t7;\n    float u9[16];\n')
    if sa(src) != src:
        bad.append('pointer: %s' % sa(src))
    got = sd(sa(fn('    *(int *)((a4 + 0x80)) = 1;\n    *(int *)((t7 + 0x80)) = 2;\n    *(float *)((a4 + 0x40)) = 0.0f;\n')))
    if got != ['struct o40_float { char p[0x40]; float v; };', 'struct o80_int { char p[0x80]; int v; };']:
        bad.append('decls: %s' % got)
    import rewrites
    gb = rewrites.global_base
    got = gb(fn('    *(int *)0xC94D960 = *(int *)0xC94D964;\n    *(float *)0xC94D99C = 0.0f;\n    t7 = *(int *)0xC950000;\n'))
    for want in ('(((struct o0_int *)0xC94D960)->v) = (((struct o4_int *)0xC94D960)->v);', '(((struct o3C_float *)0xC94D960)->v) = 0.0f;',
                 't7 = *(int *)0xC950000;'):
        if want not in got:
            bad.append('global: %s missing in %s' % (want, got))
    if sd(got) != ['struct o0_int { int v; };', 'struct o3C_float { char p[0x3C]; float v; };', 'struct o4_int { char p[0x4]; int v; };']:
        bad.append('global decls: %s' % sd(got))
    src = fn('    *(volatile int *)0xC94D960 = 1;\n    *(volatile int *)0xC94D964 = 1;\n')
    if gb(src) != src:
        bad.append('global volatile: %s' % gb(src))
    src = fn('    *(int *)0xC94D960 = 1;\n    *(int *)0xC94DA00 = 1;\n')
    if gb(src) != src:
        bad.append('global alone: %s' % gb(src))
    src = fn('    *(unsigned int *)(((int)stk + 28)) = *(int *)((int)stk + 28);\n    *(unsigned int *)(((int)stk + 24)) = *(int *)((int)stk + 28);\n'
             '    *(short *)(((int)stk + 8)) = *(int *)((int)stk + 8);\n')
    got = rewrites.drop_self_copies(src)
    if '+ 28)) = *(int *)((int)stk + 28)' in got or '+ 24)) = *(int *)((int)stk + 28)' not in got or '+ 8)) = *(int *)((int)stk + 8)' not in got:
        bad.append('self: %s' % got)
    unit = ('/* unit */\nextern int g(int);\n\nint f(int a4)\n{\n    return *(int *)((a4 + 0x2D4));\n}\n\n'
            'int h(int a4)\n{\n    return g(a4);\n}\n')
    new = {'f': sa('int f(int a4)\n{\n    return *(int *)((a4 + 0x2D4));\n}\n')}
    got = rewrites.splice(unit, new)
    want = ('/* unit */\nextern int g(int);\nstruct o2D4_int { char p[0x2D4]; int v; };\n\n\n'
            'int f(int a4)\n{\n    return (((struct o2D4_int *)(a4))->v);\n}\n\nint h(int a4)\n{\n    return g(a4);\n}\n')
    if got != want:
        bad.append('replace/decls:\n%s' % got)
    if rewrites.splice(got, new) != got:
        bad.append('again')
    if rewrites.splice(unit, {'h': 'int h(int a4)\n{\n    return g(a4 + 1);\n}\n'}).count('struct ') != 0:
        bad.append('none')
    defs = rewrites.definitions(['int g(int a4, int a5)\n{\n    return a4;\n}\n', 'void h(void)\n{\n}\n'])
    if defs != {'g': ['int', 'int'], 'h': []}:
        bad.append('definitions: %s' % defs)
    unit = ('int g(int, int, int, int, int);\nint h(int, int, int, int);\nint p(int, ...);\nint q(float, int, int);\n\nint f(int a4)\n{\n'
            '    h(R4, R5, R6, R7);\n    p(1, 2, 3);\n    return g(a4, 2, R6, *(int *)((int)stk + 8), k(1)) + g(a4, 3, R6, R7, 0);\n}\n')
    got, names = rewrites.narrow_calls(unit, dict(defs, p=['int'], q=['int']))
    if names != ['h'] or 'int h(void);' not in got or '    h();' not in got:
        bad.append('narrow: %s %s' % (names, got))
    if 'int g(int, int, int, int, int);' not in got or 'g(a4, 2, R6, *(int *)((int)stk + 8), k(1))' not in got or 'g(a4, 3, R6, R7, 0)' not in got:
        bad.append('keepcall: %s' % got)
    got2, names2 = rewrites.narrow_calls(unit.replace(', k(1))', ', 1)'), defs)
    if 'g' not in names2 or 'int g(int, int);' not in got2 or 'g(a4, 2)' not in got2 or 'g(a4, 3)' not in got2:
        bad.append('narrow g: %s %s' % (names2, got2))
    if 'int q(float, int, int);' not in got:
        bad.append('types: %s' % got)
    if 'int p(int, ...);' not in got or 'p(1, 2, 3);' not in got:
        bad.append('vararg: %s' % got)
    # merge_copies: a result threaded through nesting levels by tA = (tB); copies
    src = fn('    t70 = 0;\n    if (a4) {\n        t30 = 0;\n        if (a4 > 1) {\n            t30 = 5;\n        }\n        t70 = (t30);\n    }\n    return t70;\n', '    int t70;\n    int t30;\n')
    got = rewrites.merge_copies(src)
    if 't30' in got or '        t70 = 0;\n' not in got or '            t70 = 5;\n' not in got or got.count('t70 = (t70)'):
        bad.append('merge: %s' % got)
    src = fn('    t70 = 0;\n    t30 = f();\n    if (a4) {\n        goto L_1;\n    }\n    t70 = (t30);\n    L_1:;\n    return t70;\n', '    int t70;\n    int t30;\n')
    if rewrites.merge_copies(src) != src:
        bad.append('merge goto: %s' % rewrites.merge_copies(src))
    src = fn('    t30 = f();\n    t70 = (t30);\n    return t70 + t30;\n', '    int t70;\n    int t30;\n')
    if rewrites.merge_copies(src) != src:
        bad.append('merge live: %s' % rewrites.merge_copies(src))
    src = fn('    t30 = f();\n    g(t70);\n    t70 = (t30);\n    return t70;\n', '    int t70;\n    int t30;\n')
    if rewrites.merge_copies(src) != src:
        bad.append('merge tA used: %s' % rewrites.merge_copies(src))
    # chains_to_switch: a state chain on one variable as a switch
    src = fn('    t0 = a4;\n    if (t0 != 0) {\n        if (t0 != 1) {\n            if (t0 != 2) {\n                return t0;\n            }\n            g(2);\n        } else {\n            g(1);\n            return 1;\n        }\n    } else {\n        g(0);\n    }\n    return 0;\n', '    int t0;\n')
    got = rewrites.chains_to_switch(src)
    want = ('    switch (t0) {\n    case 0:\n        g(0);\n        break;\n    case 1:\n        g(1);\n        return 1;\n    case 2:\n        g(2);\n        break;\n'
            '    default:\n        return t0;\n    }\n')
    if want not in got:
        bad.append('switch: %s' % got)
    src2 = fn('    if (t0 == 3) {\n        g(3);\n    } else {\n        if (t0 == 4) {\n            g(4);\n        } else {\n            if (t0 == 5) {\n                g(5);\n            }\n        }\n    }\n', '    int t0;\n')
    got = rewrites.chains_to_switch(src2)
    if 'switch (t0) {' not in got or 'case 5:\n        g(5);\n        break;\n    }' not in got or 'default' in got:
        bad.append('switch ==: %s' % got)
    src3 = src.replace('            g(2);\n', '            break;\n')
    if rewrites.chains_to_switch(src3) != src3:
        bad.append('switch break: %s' % rewrites.chains_to_switch(src3))
    src4 = fn('    if (t0 != 0) {\n        if (t0 != 1) {\n            g(9);\n        } else {\n            g(1);\n        }\n    } else {\n        g(0);\n    }\n', '    int t0;\n')
    if rewrites.chains_to_switch(src4) != src4:
        bad.append('switch short: %s' % rewrites.chains_to_switch(src4))
    # drop_dead_frame: a stack array nothing reads goes, with its stores and bare volatile reads
    t = ('int f(int a4)\n{\n    int t1;\n    int stk[6];\n\n    t1 = a4 + 1;\n    *(int *)((int)stk + 4) = t1;\n    *(unsigned int *)(((int)stk + 8)) = a4;\n'
         '    *(volatile int *)((int)stk + 4);\n    return g(t1);\n}\n')
    got = rewrites.drop_dead_frame(t)
    if 'stk' in got or 'return g(t1);' not in got or 't1 = a4 + 1;' not in got or '    int t1;\n\n' not in got:
        bad.append('dead frame: %s' % got)
    for name, src in (('read', t.replace('return g(t1);', 'return *(int *)((int)stk + 4);')),
                      ('address', t.replace('return g(t1);', 'return g(((int)stk + 4));')),
                      ('call', t.replace('= a4;\n', '= h(a4);\n')),
                      ('volatile rhs', t.replace('= a4;\n', '= *(volatile int *)0xFFFFFFE0;\n'))):
        if rewrites.drop_dead_frame(src) != src:
            bad.append('dead frame %s: a function that needs its frame changed' % name)
    if rewrites.drop_dead_frame(got) != got:
        bad.append('dead frame twice: a second run changed the text')
    # hoist_builtins: a pure builtin called with the same variable more than once is computed once
    t = ('int f(int a4)\n{\n    float u0;\n    float u5;\n\n    u5 = *(float *)(a4 + 0);\n    u5 = u5 * u5;\n    if (_builtin_sqrtf(u5) > 1.0f) {\n        return 0;\n    }\n'
         '    if (_builtin_sqrtf(u5) > 2.0f) {\n        return 1;\n    }\n    return _builtin_sqrtf(u5) > 3.0f;\n}\n')
    got = rewrites.hoist_builtins(t)
    if got.count('_builtin_sqrtf(u5)') != 1 or 'float s1;' not in got or '    s1 = _builtin_sqrtf(u5);\n    if (s1 > 1.0f) {' not in got or 'return s1 > 3.0f;' not in got:
        bad.append('hoist: %s' % got)
    t2 = t.replace('    u5 = u5 * u5;\n', '    u5 = u5 * u5;\n    if (a4) {\n        u5 = u5 + 1.0f;\n    }\n').replace('    return _builtin_sqrtf(u5) > 3.0f;', '    u5 = 2.0f;\n    return _builtin_sqrtf(u5) > 3.0f;')
    if rewrites.hoist_builtins(t2) != t2:
        bad.append('hoist reassigned: the argument changes between the calls')
    t3 = t.replace('    if (_builtin_sqrtf(u5) > 1.0f) {', '    for (;;) {\n        if (_builtin_sqrtf(u5) > 1.0f) {\n            break;\n        }\n    }\n    if (u5 > 1.0f) {')
    if rewrites.hoist_builtins(t3) != t3:
        bad.append('hoist loop: a function with a loop changed')
    t4 = t.replace('_builtin_sqrtf(u5)', '_builtin_sqrtf(u5 + 1.0f)')
    if rewrites.hoist_builtins(t4) != t4:
        bad.append('hoist expr: a call whose argument is an expression changed')
    t5 = ('int f(int a4)\n{\n    float u5;\n\n    u5 = *(float *)(a4 + 0);\n    if (a4) {\n        if (_builtin_fabsf(u5) > 1.0f) {\n            return 0;\n        }\n    } else {\n'
          '        if (_builtin_fabsf(u5) > 2.0f) {\n            return 1;\n        }\n    }\n    return 2;\n}\n')
    if rewrites.hoist_builtins(t5) != t5:
        bad.append('hoist branches: calls in sibling branches changed')
    if rewrites.hoist_builtins(got) != got:
        bad.append('hoist twice: a second run changed the text')
    # frame_rebase: the stack array based at its first used word
    t = ('int f(int a4)\n{\n    int stk[16];\n\n    *(unsigned int *)(((int)stk + 4)) = a4;\n    *(float *)(((int)stk + 12)) = 1.0f;\n'
         '    return g(((int)stk + 4), *(int *)((int)stk + 8 + 4));\n}\n\nint h(int a4)\n{\n    int stk[6];\n\n    *(int *)(((int)stk + 8)) = a4;\n    return g(((int)stk + 8));\n}\n')
    got = rewrites.frame_rebase(t)
    for want in ('int stk[15];', '*(unsigned int *)(((int)stk + 0)) = a4;', '*(float *)(((int)stk + 8)) = 1.0f;', 'g(((int)stk + 0), *(int *)((int)stk + 4 + 4))',
                 'int stk[4];', '*(int *)(((int)stk + 0)) = a4;'):
        if want not in got:
            bad.append('rebase: %r missing in %s' % (want, got))
    t2 = 'int f(int a4)\n{\n    int stk[8];\n\n    *(int *)(((int)stk + 0)) = a4;\n    *(int *)(((int)stk + 8)) = a4;\n}\n'
    if rewrites.frame_rebase(t2) != t2:
        bad.append('rebase zero: a function whose first slot is 0 changed')
    t3 = 'int f(int a4)\n{\n    int stk[8];\n\n    stk[1] = a4;\n    *(int *)(((int)stk + 8)) = a4;\n}\n'
    if rewrites.frame_rebase(t3) != t3:
        bad.append('rebase index: a function that indexes stk changed')
    t4 = 'int f(int a4)\n{\n    int stk[8];\n\n    *(int *)(((int)stk + 6)) = a4;\n}\n'
    if rewrites.frame_rebase(t4) != t4:
        bad.append('rebase odd: an offset that is not a word multiple changed')
    if rewrites.frame_rebase(got) != got:
        bad.append('rebase twice: a second run changed the text')
    # narrow_unit: the generator's hook, read once from a scratch src/ (a temp repo), and the line count unchanged (gen_pipe's spans)
    import tempfile
    import shutil
    tmp = tempfile.mkdtemp()
    cwd = os.getcwd()
    try:
        os.makedirs(os.path.join(tmp, 'src'))
        open(os.path.join(tmp, 'src', 'gen_x.c'), 'w').write('int h(void)\n{\n    return 1;\n}\n')
        os.chdir(tmp)
        rewrites._DEFS[:] = []
        t = 'int h(int, int, int, int);\n\nint f(int a4)\n{\n    return h(R4, R5,\n        R6, R7) + a4;\n}\n'
        got = rewrites.narrow_unit(t)
        if 'int h(void);' not in got or 'h()' not in got or got.count('\n') != t.count('\n'):
            bad.append('narrow_unit: %r' % got)
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp)
    got = rewrites.by_function_size({'a.c': ['s', 'm'], 'b.c': ['l'], 'c.c': ['t']}, {'s': 40, 'm': 300, 'l': 900, 't': 10}, 256)
    if got != ['b.c', 'a.c']:
        bad.append('by_function_size: largest function first, a unit with none of the size left out: %r' % got)
    if rewrites.function_names('int f(int a)\n{\n}\nint g(void);\nvoid h(void)\n{\n}\n') != ['f', 'h']:
        bad.append('function_names: definitions only')
    if bad:
        sys.exit('[ERROR] rewrites check failed:\n' + '\n'.join(bad))
    print('[rewrites] ok: self-copies go, far fields and nearby globals are structure members, over-wide callees narrowed, units take them once')


if __name__ == '__main__':
    main()
