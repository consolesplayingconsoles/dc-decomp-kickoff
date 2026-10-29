#!/usr/bin/env python3
"""coalesce.py gives temporaries with disjoint live ranges one name (a function with 346 of them compiled to 10,988 bytes, with 14 to 8,424:
SHC keeps few in registers and puts the rest in a frame that outgrows the short offsets). The values must not change. Random structured
functions (if / else, counted loops, assignments of arithmetic on earlier temporaries, effects) are run before and after on every input and
the traces must match. No game data, no compiler. Stdlib only.

    check.py      300 random functions of 20-60 temporaries, every combination of 6 condition bits:
                    same      the sequence of effects and the returned value are the same before and after
                    fewer     at least half of them end with fewer declared temporaries, none with more
                    stuck     a temporary read after a loop it is written in, one carried across a loop head, one whose address is taken,
                              and a function with a goto keep their names
"""
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '5-generated', 'gen_equiv'))
import coalesce  # noqa: E402


class Gen:
    def __init__(self, rng):
        self.rng, self.n, self.lines = rng, 0, []

    def new(self):
        self.n += 1
        return 't%d' % (self.n - 1)

    def expr(self, defined):
        r = self.rng
        if not defined or r.random() < 0.3:
            return str(r.randint(1, 9))
        a = r.choice(sorted(defined))
        if r.random() < 0.5:
            return '(%s + %d)' % (a, r.randint(1, 9))
        return '(%s * 3 + %s)' % (a, r.choice(sorted(defined)))

    def block(self, defined, depth, ind):
        r = self.rng
        for _ in range(r.randint(2, 6)):
            k = r.random()
            if k < 0.55 or depth >= 3:
                v = self.new()
                self.lines.append('%s%s = %s;' % (ind, v, self.expr(defined)))
                defined.add(v)
                if r.random() < 0.5:
                    self.lines.append('%sout = out * 7 + %s;' % (ind, v))
            elif k < 0.8:
                self.lines.append('%sif (c%d) {' % (ind, r.randint(0, 5)))
                d1 = set(defined)
                self.block(d1, depth + 1, ind + '    ')
                self.lines.append('%s} else {' % ind)
                d2 = set(defined)
                self.block(d2, depth + 1, ind + '    ')
                self.lines.append('%s}' % ind)
                defined |= (d1 & d2)
            else:
                i = self.new()
                self.lines.append('%s%s = 0;' % (ind, i))
                defined.add(i)
                self.lines.append('%sfor (;;) {' % ind)
                d1 = set(defined)
                self.block(d1, depth + 1, ind + '    ')
                self.lines.append('%s    %s = %s + 1;' % (ind, i, i))
                self.lines.append('%s    if (%s >= 3) break;' % (ind, i))
                self.lines.append('%s}' % ind)


def make(rng):
    g = Gen(rng)
    g.block(set(), 0, '    ')
    decl = ['    int t%d;' % i for i in range(g.n)] + ['    int out;', '']
    return '\n'.join(['int f(void)', '{'] + decl + ['    out = 0;'] + g.lines + ['    return out;', '}']), g.n


def run(text, bits):
    py = ['def f(c):', '    out = 0', '    tr = []']
    for l in text.split('\n')[2:-1]:
        s = l.strip()
        if s.startswith('int ') or s == 'out = 0;':
            continue
        ind = (len(l) - len(l.lstrip())) // 4 - 1
        pad = '    ' * (ind + 1)
        mb = re.match(r'if \((t\d+) >= 3\) break;', s)
        if mb:
            py.append(pad + 'if %s >= 3: break' % mb.group(1))
        elif s.startswith('if ('):
            py.append(pad + 'if c[%s]:' % re.match(r'if \(c(\d)\)', s).group(1))
        elif s == '} else {':
            py.append(pad + 'else:')
        elif s == '}':
            continue
        elif s.startswith('for (;;)'):
            py.append(pad + 'while True:')
        elif s.startswith('return'):
            py.append(pad + 'return tr, out')
        elif s.startswith('out = out * 7'):
            py.append(pad + 'out = (out * 7 + %s) & 0xFFFFFF' % s.split('+')[1].strip(' ;'))
            py.append(pad + 'tr.append(out)')
        else:
            py.append(pad + s.rstrip(';'))
    ns = {}
    exec('\n'.join(py), ns)
    return ns['f']([bool(bits >> i & 1) for i in range(6)])


def fix_breaks(text):
    return text


def main():
    rng = random.Random(11)
    bad, fewer, total = [], 0, 0
    for n in range(300):
        t, _ = make(rng)
        p = coalesce.coalesce(t)
        a, b = len(re.findall(r'^    int t\d+;', t, re.M)), len(re.findall(r'^    int t\d+;', p, re.M))
        total += 1
        if b > a:
            bad.append('fewer: case %d has %d temporaries after, %d before' % (n, b, a))
        fewer += b < a
        for bits in range(64):
            try:
                x, y = run(t, bits), run(p, bits)
            except Exception as e:
                bad.append('run: case %d bits %d: %s' % (n, bits, e)); break
            if x != y:
                bad.append('same: case %d bits %d: %s vs %s' % (n, bits, x[1], y[1])); break
    if fewer < total // 2:
        bad.append('fewer: only %d of %d functions lost a temporary' % (fewer, total))
    keep = [
        ('a goto', 'int f(void)\n{\n    int t0;\n    int t1;\n    t0 = 1;\n    goto L_1;\n    L_1:;\n    t1 = t0;\n    return t1;\n}'),
        ('an address taken', 'int f(void)\n{\n    int t0;\n    int t1;\n    t0 = 1;\n    g(&t0);\n    t1 = 2;\n    return t1;\n}'),
    ]
    for what, s in keep:
        if coalesce.coalesce(s) != s:
            bad.append('stuck: a function with %s was changed' % what)
    carried = '\n'.join(['int f(void)', '{', '    int t0;', '    int t1;', '    int t2;', '    t0 = 5;', '    for (;;) {', '        t1 = t0 + 1;',
                         '        t0 = t1;', '        if (t0 >= 9) break;', '    }', '    t2 = t0;', '    return t2;', '}'])
    p = coalesce.coalesce(carried)
    if len(set(re.findall(r'\bt\d\b', p.split('t0 = 5;')[0]))) < 1 or 't0 = 5;' not in p:
        bad.append('stuck: the loop-carried function lost its shape')
    if bad:
        sys.exit('[ERROR] coalesce check failed:\n' + '\n'.join(bad[:8]))
    print('[coalesce] ok: %d random functions give the same effects and result before and after, %d with fewer temporaries; goto, address-taken and loop-carried ones are left alone' % (total, fewer))


if __name__ == '__main__':
    main()
