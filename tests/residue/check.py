#!/usr/bin/env python3
"""What the bloated functions share (scripts/tools/7-reduction/residue.py): the C line shapes much more common in the functions whose
C is far over the original than in the ones that came out near it. No game data, no compiler. Stdlib only.

    check.py      normalize() and contrast() on made-up functions:
                    shape     numbers, temporaries, argument names and callee names are one placeholder each; the structure stays
                    rank      a shape in every bloated function and no fine one ranks first, with its counts and the excess of the
                              functions that have it; a shape in both groups equally ranks near 1
                    support   a shape in fewer than min_support bloated functions is not listed
                    select    functions() splits a file into its definitions; select() puts a function at 1.2x or more in the bloated
                              group, at 1.1x or less in the fine group, in neither between them, and leaves out hand-written ones
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '7-reduction'))
import residue  # noqa: E402


def main():
    bad = []
    n = residue.normalize('    *(unsigned int *)((a4 + 0x1C4)) = FUN_0c01ff28(t17, 0xC1F79B4, 2.5f);')
    if n != '*(unsigned int *)((A + N)) = F(T, N, N);':
        bad.append('shape: %r' % n)
    src = ''.join('int B%d(int a4)\n{\n    int t1;\n\n    t1 = g(a4);\n    t1 = t1 + 1;\n    h(t1, %d);\n    return k(t1);\n}\n\n' % (i, i) for i in range(4))
    src += ''.join('int F%d(int a4)\n{\n    int t1;\n\n    t1 = g(a4);\n    h(t1, %d);\n    return k(t1);\n}\n\n' % (i, i) for i in range(4))
    funcs = residue.functions(src)
    if sorted(funcs) != sorted(['B%d' % i for i in range(4)] + ['F%d' % i for i in range(4)]):
        bad.append('functions: %r' % sorted(funcs))
    sizes = {}
    for i in range(4):
        sizes['B%d' % i] = (100, 130)          # 1.3x: bloated
        sizes['F%d' % i] = (100, 104)          # 1.04x: fine
    sizes['M'] = (100, 115)                    # 1.15x: neither
    funcs['M'] = funcs['F0']
    sizes['H'] = (100, 300)                    # hand-written: left out
    funcs['H'] = funcs['B0']
    bloated, fine = residue.select(funcs, sizes, 1.2, 1.1, hand={'H'})
    if sorted(bloated) != ['B0', 'B1', 'B2', 'B3'] or sorted(fine) != ['F0', 'F1', 'F2', 'F3']:
        bad.append('select: bloated %r fine %r' % (sorted(bloated), sorted(fine)))
    rows = residue.contrast(bloated, fine, sizes, min_support=3)
    if not rows or rows[0][4] != 'T = T + N;' or rows[0][1] != 4 or rows[0][2] != 0 or rows[0][3] != 120:
        bad.append('rank: %r' % (rows[:2],))
    if any(r[4] == 'h(T, N);' and r[0] > 1.5 for r in rows):
        bad.append('rank: a shape in both groups ranks high: %r' % (rows,))
    if residue.contrast(bloated, fine, sizes, min_support=5):
        bad.append('support: shapes below min_support are listed')
    if bad:
        sys.exit('[ERROR] residue check failed:\n' + '\n'.join(bad))
    print('[residue] ok: shapes are normalised, the ones only the bloated functions have rank first, hand-written functions are left out')


if __name__ == '__main__':
    main()
