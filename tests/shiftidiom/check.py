#!/usr/bin/env python3
"""textpass.shift_idiom rewrites the reader's shift by a register (the shad / shld ternary, 19 instructions from SHC) as one C shift,
`((int)y << (int)x)` or `((unsigned int)y << (int)x)`, which SHC compiles to the one shad or shld the original had (measured: six Crazy
Taxi files 14,532 -> 13,348 bytes, every one smaller). gen_core writes the short form since 2026-10-30. No game data, no compiler.

    check.py      lifts shift_idiom and _SHIFT from textpass.py (that module needs a repo):
                    forms      the signed and the unsigned ternary are rewritten, with a plain and a parenthesised operand
                    values     for every count -40..40 the ternary (as C would evaluate it) equals the SH-4's shad / shld
                    stuck      another ternary, and a ternary whose two operands differ, are left as they were
"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '7-reduction', 'textpass.py')
M = 0xFFFFFFFF


def lift():
    text = open(SRC, encoding='utf-8').read()
    ns = {'re': re}
    for node in ast.parse(text).body:
        if isinstance(node, (ast.Assign, ast.For)) and re.search(r'\b_B\b|\b_SHIFT\b', ast.get_source_segment(text, node) or ''):
            exec(compile(ast.Module(body=[node], type_ignores=[]), SRC, 'exec'), ns)     # _B is built by a loop, _SHIFT from it
        if isinstance(node, ast.FunctionDef) and node.name == 'shift_idiom':
            exec(compile(ast.Module(body=[node], type_ignores=[]), SRC, 'exec'), ns)
    return ns['shift_idiom']


def s32(v):
    v &= M
    return v - (1 << 32) if v & 0x80000000 else v


def shad(y, x):
    """SH-4 shad: x >= 0 shifts left by x & 31; else arithmetic right by (-x) & 31, or the sign alone when that is 0"""
    x = s32(x)
    if x >= 0:
        return (y << (x & 31)) & M
    k = (-x) & 31
    return (s32(y) >> k) & M if k else (s32(y) >> 31) & M


def shld(y, x):
    x = s32(x)
    if x >= 0:
        return (y << (x & 31)) & M
    k = (-x) & 31
    return ((y & M) >> k) if k else 0


def ternary_signed(y, x):
    """the ternary as C evaluates it (int y, int x)"""
    xi, yi = s32(x), s32(y)
    if xi >= 0:
        return (yi << (xi & 31)) & M
    if (-xi) & 31:
        return (yi >> ((-xi) & 31)) & M
    return (yi >> 31) & M


def ternary_unsigned(y, x):
    xi = s32(x)
    if xi >= 0:
        return (y << (xi & 31)) & M
    if (-xi) & 31:
        return ((y & M) >> ((-xi) & 31)) & M
    return 0


def main():
    shift_idiom = lift()
    bad = []
    T = '(((int)%s >= 0) ? (%s << (%s & 31)) : ((-(int)%s & 31) ? ((%s)%s >> (-(int)%s & 31)) : %s))'
    sg = lambda x, y: T % (x, y, x, x, 'int', y, x, '((int)%s >> 31)' % y)
    un = lambda x, y: T % (x, y, x, x, 'unsigned int', y, x, '0')
    cases = {
        'signed, plain operands': ('t = ' + sg('R4', 'R10') + ';', 't = ((int)R10 << (int)R4);'),
        'unsigned, plain operands': ('t = ' + un('R4', 'R10') + ';', 't = ((unsigned int)R10 << (int)R4);'),
        'signed, parenthesised count': ('t = ' + sg('(t20 & R8)', 'R10') + ';', 't = ((int)R10 << (int)(t20 & R8));'),
        'signed, negated count and compound value': ('R4 = (' + sg('(-t26)', '(R6 - 1)') + ' + 0x1);', 'R4 = (((int)(R6 - 1) << (int)(-t26)) + 0x1);'),
        'a read of memory as the value': ('x = ' + sg('R4', '(*(int *)(((int)stk + 8)))') + ';', 'x = ((int)(*(int *)(((int)stk + 8))) << (int)R4);'),
    }
    for k, (src, want) in cases.items():
        got = shift_idiom(src)
        if got != want:
            bad.append('forms, %s:\n    %s\n    wanted %s' % (k, got, want))
    for k, (src) in {'another ternary': 't = ((a >= 0) ? (b << 2) : (b >> 2));',
                     'operands that differ': 't = ' + (T % ('R4', 'R10', 'R5', 'R4', 'int', 'R10', 'R4', '((int)R10 >> 31)')) + ';'}.items():
        if shift_idiom(src) != src:
            bad.append('stuck, %s: was changed to %s' % (k, shift_idiom(src)))
    for y in (0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF, 0x12345678, 0xDEADBEEF):
        for x in list(range(-40, 41)) + [0x7FFFFFFF, 0x80000000]:
            if ternary_signed(y, x) != shad(y, x):
                bad.append('values: signed ternary %08X by %d gives %08X, shad %08X' % (y, s32(x), ternary_signed(y, x), shad(y, x)))
            if ternary_unsigned(y, x) != shld(y, x):
                bad.append('values: unsigned ternary %08X by %d gives %08X, shld %08X' % (y, s32(x), ternary_unsigned(y, x), shld(y, x)))
    if bad:
        sys.exit('[ERROR] shiftidiom check failed:\n' + '\n'.join(bad[:12]))
    print('[shiftidiom] ok: the signed and unsigned shift ternaries become one C shift (plain, parenthesised, negated and memory operands);'
          ' another ternary and mismatched operands stay; the ternary equals shad / shld for every count -40..40 and the extremes')


if __name__ == '__main__':
    main()
