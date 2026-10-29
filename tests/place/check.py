#!/usr/bin/env python3
"""place.py moves a block to the only goto that reaches it, so a flat-form function has fewer labels (SHC stops at about 512). The
behaviour must not change. Random flat functions (labels, `if (cN) goto L;`, plain gotos, returns, fall-through) are run before and
after on every input and the traces must match. No game data, no compiler. Stdlib only.

    check.py      200 random functions of 12-40 blocks, every combination of 8 condition bits:
                    same      the sequence of effect statements and the returned value are the same before and after
                    fewer     labels went down in at least half of them, and never up
                    stuck     a block with two jumps into it, one that is fallen into, a self-loop and the first block stay
"""
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '5-generated', 'gen_equiv'))
import place  # noqa: E402


def gen(rng):
    n = rng.randint(12, 40)
    L = ['    L_%04X:;' % (0x100 + k) for k in range(n)]
    lines = ['void f(void)', '{', '    int out;', '    out = 0;']
    for k in range(n):
        lines.append(L[k])
        for e in range(rng.randint(0, 2)):
            lines.append('    out = out * 3 + %d;' % rng.randint(1, 9))
        for c in range(rng.choice((0, 0, 1, 2))):
            lines.append('    if (c%d) goto L_%04X;' % (rng.randint(0, 7), 0x100 + rng.randrange(n)))
        r = rng.random()
        if r < 0.45:
            lines.append('    goto L_%04X;' % (0x100 + rng.randrange(n)))
        elif r < 0.6 or k == n - 1:
            lines.append('    return out;')
    lines.append('}')
    return '\n'.join(lines)


def run(text, bits):
    ls = text.split('\n')
    idx = {}
    for i, l in enumerate(ls):
        m = re.match(r'^\s*(L_[0-9A-F]+):;', l)
        if m:
            idx[m.group(1)] = i
    out, pc, steps, trace = 0, 0, 0, []
    while pc < len(ls) and steps < 4000 and len(trace) < 60:
        steps += 1
        l = ls[pc].strip()
        pc += 1
        m = re.match(r'^out = out \* 3 \+ (\d+);$', l)
        if m:
            out = (out * 3 + int(m.group(1))) & 0xFFFFFF
            trace.append(out)
            continue
        m = re.match(r'^if \(c(\d)\) goto (L_\w+);$', l)
        if m:
            if bits >> int(m.group(1)) & 1:
                pc = idx[m.group(2)]
            continue
        m = re.match(r'^if \(!\(c(\d)\)\) goto (L_\w+);$', l)
        if m:
            if not bits >> int(m.group(1)) & 1:
                pc = idx[m.group(2)]
            continue
        m = re.match(r'^goto (L_\w+);$', l)
        if m:
            pc = idx[m.group(1)]
            continue
        if l == 'return out;':
            return trace, out
    return trace, None


def main():
    rng = random.Random(7)
    bad, fewer, total = [], 0, 0
    for n in range(200):
        t = gen(rng)
        p = place.place(t)
        a, b = t.count(':;'), p.count(':;')
        total += 1
        if b > a:
            bad.append('fewer: case %d has %d labels after, %d before' % (n, b, a))
        if b < a:
            fewer += 1
        for bits in range(256):
            x, y = run(t, bits), run(p, bits)
            if x[1] is None or y[1] is None:                      # cut off (a loop): the effects so far must agree
                m = min(len(x[0]), len(y[0]))
                ok = x[0][:m] == y[0][:m]
            else:
                ok = x == y
            if not ok:
                bad.append('same: case %d bits %d: %s... vs %s...' % (n, bits, x[0][:6], y[0][:6])); break
    if fewer < total // 2:
        bad.append('fewer: only %d of %d functions lost a label' % (fewer, total))
    s = '\n'.join(['void f(void)', '{', '    out = 0;', '    L_0001:;', '    if (c0) goto L_0002;', '    goto L_0003;', '    L_0002:;',
                   '    return out;', '    L_0003:;', '    if (c1) goto L_0003;', '    L_0004:;', '    return out;', '}'])
    p = place.place(s)
    for lab in ('L_0001', 'L_0002', 'L_0003'):
        if lab + ':;' not in p:
            bad.append('stuck: %s was moved though it has two jumps in, a jump from the if above it, or is the first block' % lab)
    if bad:
        sys.exit('[ERROR] place check failed:\n' + '\n'.join(bad[:8]))
    print('[place] ok: %d random functions behave the same before and after (loops compared on their first 60 effects) on all inputs, %d lost labels, shared blocks stay' % (total, fewer))


if __name__ == '__main__':
    main()
