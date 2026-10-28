#!/usr/bin/env python3
"""A flat-form function with more labels than the compiler takes is written as a main function and helper parts
(scripts/tools/5-generated/gen_equiv/splitflat.py). No game data, no compiler: the C is checked by its structure. Stdlib only.

    check.py      a synthetic flat function of 12 blocks, split at 4 labels:
                    under     a function under the limit comes back as it was
                    first     the text still starts with the main function's own header (the file head takes it for the prototype)
                    within    every goto lands on a label of the same function; no function holds more labels and cases than the limit
                    handover  a jump to another part's block is a hand-over (NEXT_ in main, a return of the block in a part), and a
                              part's own return hands its value back and returns -1
                    state     every local and parameter is a word of the shared array (S_), and is #undef'd at the end
                    wired     gen_drv.build passes what it writes through split (cpuChasePlan split at 150 labels by hand: Equivalent
                              on its 108 cases, the same 2,789 instructions)
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '5-generated', 'gen_equiv'))
import splitflat  # noqa: E402


def flat(n):
    out = ['int fn(int a4, int a5)', '{', '    int t0;', '    float u1;', '    int stk[8];', '', '    int R0;', '    float F2;', '    int T_;',
           '    R0 = a4;', '    goto L_100;']
    for i in range(n):
        out += ['    L_%X:;' % (0x100 + i), '    t0 = R0 + %d;' % i, '    stk[1] = t0;', '    F2 = (float)a5;',
                '    if ((t0 > 9)) goto L_%X;' % (0x100 + (i * 7 + 3) % n)]
        out += ['    return t0;'] if i == n - 1 else ['    goto L_%X;' % (0x100 + i + 1)]
    return '\n'.join(out + ['}'])


def functions(text):
    """{name: body} of every function definition in the text"""
    out = {}
    for m in re.finditer(r'^(?:int|void|float) (\w+)\([^)]*\)\n\{\n', text, re.M):
        end = re.compile(r'^\}', re.M).search(text, m.end()).start()
        out[m.group(1)] = text[m.end():end]
    return out


def main():
    bad = []
    small = flat(3)
    if splitflat.split(small, 4) != small:
        bad.append('under: a function under the limit was changed')
    big = flat(12)
    s = splitflat.split(big, 4)
    if not s.startswith('int fn(int p_a4, int p_a5)\n{'):
        bad.append('first: the text does not start with the main header: %r' % s[:40])
    fs = functions(s)
    if len(fs) < 3:
        bad.append('within: %d functions, want the main one and parts' % len(fs))
    for n, b in fs.items():
        labs = set(re.findall(r'^\s*(L_[0-9A-F]+|X_):;', b, re.M))
        cases = len(re.findall(r'\bcase \d+:', b))
        for g in re.findall(r'\bgoto (L_[0-9A-F]+|X_);', b):
            if g not in labs:
                bad.append('within: %s jumps to %s, which it does not hold' % (n, g))
        if len(labs) + cases > 4 * 2 + 2:
            bad.append('within: %s holds %d labels and %d cases' % (n, len(labs), cases))
    parts = [n for n in fs if n != 'fn']
    if not any('return -1;' in fs[p] and re.search(r'S_\[\d+\] = t0; return -1;', fs[p]) for p in parts):
        bad.append('handover: no part hands back the function return')
    if 'NEXT_ = ' not in fs.get('fn', '') or not any(re.search(r'\breturn \d+;', fs[p]) for p in parts):
        bad.append('handover: no hand-over between parts')
    for v in ('t0', 'u1', 'stk', 'R0', 'F2', 'T_', 'a4', 'a5'):
        if not re.search(r'#define %s \(' % v, s) or '#undef %s' % v not in s:
            bad.append('state: %s is not a word of the shared array' % v)
    if 'splitflat.split(' not in open(os.path.join(os.path.dirname(splitflat.__file__), 'gen_drv.py')).read():
        bad.append('wired: gen_drv.build does not split what it writes')
    if bad:
        sys.exit('[ERROR] splitflat check failed:\n' + '\n'.join(bad[:10]))
    print('[splitflat] ok: a flat function over the label limit is a main function and parts, every jump inside its own function')


if __name__ == '__main__':
    main()
