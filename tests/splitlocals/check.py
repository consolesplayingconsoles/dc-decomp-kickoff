#!/usr/bin/env python3
"""splitflat.local_vars decides which scalar locals of a function split into parts can be real locals of one part instead of words of the shared
array (Virtua Tennis cpuSglAimTable: 865 labels, 46,444 bytes over, every local a load and a store). A part function is called again at
each hand-over and its locals start over, so a variable may only be local when it is written before it is read on every path from every
place its part is entered. This checks the decision by running: random flat programs (labels, assignments, `if (cN) goto L;`, gotos,
returns), split into parts of 4 blocks, are run with every local destroyed whenever control leaves its part; reading a destroyed value is a
wrong decision. No game data, no compiler. Stdlib only.

    check.py      500 random programs of 10-24 blocks, 8-18 variables, every combination of 6 condition bits:
                    safe      no run reads a variable that local_vars made local after control left its part
                    some      at least a tenth of the programs have at least one variable made local
                    kept      a variable written in one part and read in another, and one read before written on re-entry, stay in the array
"""
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get('SPLITFLAT_DIR') or os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '5-generated', 'gen_equiv'))
import splitflat  # noqa: E402

PER = 4


def make(rng):
    nb, nv = rng.randint(10, 24), rng.randint(8, 18)
    names = ['t%d' % i for i in range(nv)]
    blocks = []
    for b in range(nb):
        lines = ['    L_%04X:;' % (0x100 + b)]
        known = []
        for _ in range(rng.randint(2, 5)):
            r = rng.random()
            if r < 0.5 or not known:
                v = rng.choice(names)
                src = rng.choice(known) if known and rng.random() < 0.7 else None
                if src is None and rng.random() < 0.08:
                    src = rng.choice(names)                         # maybe from an earlier block
                lines.append('    %s = %s;' % (v, '(%s + %d)' % (src, rng.randint(1, 9)) if src else str(rng.randint(1, 9))))
                known.append(v)
            else:
                lines.append('    out = out * 7 + %s;' % rng.choice(known + ([rng.choice(names)] if rng.random() < 0.05 else [])))
        for _ in range(rng.choice((0, 0, 1, 1))):
            lines.append('    if (c%d) goto L_%04X;' % (rng.randint(0, 5), 0x100 + rng.randrange(nb)))
        r = rng.random()
        if r < 0.4:
            lines.append('    goto L_%04X;' % (0x100 + rng.randrange(nb)))
        elif r < 0.55 or b == nb - 1:
            lines.append('    return out;')
        blocks.append(['L_%04X' % (0x100 + b), lines])
    return names, blocks


def run(blocks, bits, owner=None, parts=None):
    """trace, result; with owner {var: part}, a variable is destroyed when control leaves its part"""
    flat, label, part_at = [], {}, []
    for bi, (lab, lines) in enumerate(blocks):
        for l in lines:
            if l.strip().endswith(':;'):
                label[lab] = len(flat)
            flat.append(l.strip())
            part_at.append(bi // PER)
    env, out, tr, pc, steps = {}, 0, [], 0, 0
    cur = 0
    while pc < len(flat) and steps < 500:
        steps += 1
        if part_at[pc] != cur:
            if owner:
                for v, p in owner.items():
                    if p == cur:
                        env[v] = None
            cur = part_at[pc]
        s = flat[pc]
        pc += 1
        m = re.match(r'^([tvw]\w*) = (.*);$', s)
        if m:
            e = m.group(2)
            vs = [x for x in re.findall(r'\b[tvw]\w*\b', e) if x not in ('out',)]
            for v in vs:
                if env.get(v) is None:
                    raise KeyError(v)
            env[m.group(1)] = eval(e, {}, dict(env)) & 0xFFFF
            continue
        m = re.match(r'^out = out \* 7 \+ ([tvw]\w*);$', s)
        if m:
            if env.get(m.group(1)) is None:
                raise KeyError(m.group(1))
            out = (out * 7 + env[m.group(1)]) & 0xFFFFFF
            tr.append(out)
            continue
        m = re.match(r'^if \(c(\d)\) goto (L_\w+);$', s)
        if m:
            if bits >> int(m.group(1)) & 1:
                pc = label[m.group(2)]
            continue
        m = re.match(r'^goto (L_\w+);$', s)
        if m:
            pc = label[m.group(1)]
            continue
        if s == 'return out;':
            return tr, out
    return tr, None


def one(per):
    global PER
    PER = per
    rng = random.Random(5)
    bad, some, total, shared = [], 0, 0, 0
    for n in range(500):
        names, blocks = make(rng)
        decls = [('int', v, 0) for v in names]
        parts = [[(b[0], b[1]) for b in blocks[i:i + PER]] for i in range(0, len(blocks), PER)]
        loc = splitflat.local_vars(decls, [], [], [(b[0], b[1]) for b in blocks], parts)
        try:
            plain = [run(blocks, bits) for bits in range(64)]
        except KeyError:
            continue                                  # reads a variable no path wrote: not a program to compare
        total += 1
        some += bool(loc)
        names, owners = splitflat.local_colors(decls, [], [], [(b[0], b[1]) for b in blocks], parts)
        if names:
            if sorted(names) != sorted(loc):
                bad.append('colors: program %d colours %s, local_vars %s' % (n, sorted(names), sorted(loc)))
            shared += len(names) - len(set(names.values()))
            rb = [[b[0], [re.sub(r'\bt\d+\b', lambda mm: names.get(mm.group(0), mm.group(0)), l) for l in b[1]]] for b in blocks]
        else:
            rb = blocks
        for bits in range(64):
            try:
                got = run(rb, bits, owners if names else loc)
            except KeyError as e:
                bad.append('safe: program %d bits %d reads %s after control left its part (local in part %s)' % (n, bits, e, loc.get(str(e).strip("'"))))
                break
            m = min(len(got[0]), len(plain[bits][0]))
            if got[0][:m] != plain[bits][0][:m]:
                bad.append('safe: program %d bits %d: trace differs' % (n, bits)); break
    if shared < 20:
        bad.append('colors: only %d variables shared a name over all programs' % shared)
    if some < total // 10:
        bad.append('some: only %d of %d programs have a local' % (some, total))
    # kept
    blocks = [['L_1', ['    L_1:;', '    t0 = 1;', '    t1 = 2;']], ['L_2', ['    L_2:;', '    out = out * 7 + t0;']],
              ['L_3', ['    L_3:;', '    t2 = 3;', '    out = out * 7 + t2;', '    if (c0) goto L_2;']], ['L_4', ['    L_4:;', '    return out;']],
              ['L_5', ['    L_5:;', '    out = out * 7 + t1;', '    t1 = 5;']]]
    decls = [('int', 't0', 0), ('int', 't1', 0), ('int', 't2', 0)]
    parts = [[(b[0], b[1]) for b in blocks[0:2]], [(b[0], b[1]) for b in blocks[2:4]], [(b[0], b[1]) for b in blocks[4:5]]]
    loc = splitflat.local_vars(decls, [], [], [(b[0], b[1]) for b in blocks], parts)
    if 't0' in loc:
        bad.append('kept: t0 is read at L_2, a block part 1 jumps to, with no write before it there: it must stay in the array')
    if 't1' in loc:
        bad.append('kept: t1 is written in part 0 and read in part 2: it must stay in the array')
    if 't2' not in loc:
        bad.append('kept: t2 (written then read inside one block) should be local')
    return bad, total, shared, some


def main():
    bad, total, shared, some = [], 0, 0, 0
    for per in (4, 1000):                  # parts of 4 blocks, and one part (a flat function that is not split)
        b, t_, s_, o_ = one(per)
        bad += ['[parts of %d] %s' % (per, x) for x in b]
        total += t_; shared += s_; some += o_
    if bad:
        sys.exit('[ERROR] splitlocals check failed:\n' + '\n'.join(bad[:8]))
    print('[splitlocals] ok: %d random runs never read a destroyed local (%d variables shared a name by colouring), %d with locals made; a value read after a re-entry stays in the array' % (total, shared, some))


if __name__ == '__main__':
    main()
