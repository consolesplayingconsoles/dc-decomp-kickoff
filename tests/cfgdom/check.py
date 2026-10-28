#!/usr/bin/env python3
"""Dominators of the reader's control-flow graph (scripts/tools/5-generated/gen_equiv/gen_cfg.py), against the set equations they
replaced. No game data. Stdlib only.

    check.py      same     on 300 random functions of bt / bf / bra / rts / plain instructions (loops that never end included): every
                           node's dominators (d in dom[n]) and immediate post-dominator (ipdom) are the ones the set equations give
                  big      a 10,000-instruction function (Virtua Tennis playerControl is about that) builds its graph in under 10 s
                  reach    reach(n) is every node a plain search from n finds, for every node; and ijoin over every branch of a
                           3,000-instruction function takes under 20 s (entryCharaSelExec, Virtua Tennis: ijoin's search for the
                           first common node recomputed reach for every pair, 56 of 60 s of its reading)
"""
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
sys.path[:0] = [os.path.join(TOOLS, '5-generated', 'gen_equiv'), os.path.join(TOOLS, '5-generated'), TOOLS]
import toolpath  # noqa: E402,F401
import gen_cfg  # noqa: E402

EXIT = gen_cfg.EXIT


def program(rng, n):
    ins = []
    for i in range(n):
        pc = 0x8C010000 + 2 * i
        r = rng.random()
        tgt = '0x%08x' % (0x8C010000 + 2 * rng.randrange(n))
        if i == n - 1 or r < 0.06: ins.append(('rts', '', pc))
        elif r < 0.30: ins.append((rng.choice(('bt', 'bf')), tgt, pc))
        elif r < 0.38: ins.append(('bra', tgt, pc))
        else: ins.append(('mov', 'r1,r2', pc))
    return ins


def reference(g):
    """The set equations: dominator sets from the entry, post-dominator sets from EXIT, ipdom as the old Graph.ipdom."""
    allset = set(g.nodes)
    dom = {n: set(allset) for n in g.nodes}; dom[0] = {0}
    ch = True
    while ch:
        ch = False
        for n in g.nodes:
            if n == 0: continue
            ps = [dom[p] for p in g.pred[n]]
            new = {n} | (set.intersection(*ps) if ps else set())
            if new != dom[n]: dom[n] = new; ch = True
    allp = set(g.nodes) | {EXIT}
    pdom = {n: set(allp) for n in g.nodes}; pdom[EXIT] = {EXIT}
    ch = True
    while ch:
        ch = False
        for n in g.nodes:
            new = {n} | set.intersection(*[pdom[t] for t in g.succ[n]])
            if new != pdom[n]: pdom[n] = new; ch = True
    def ipdom(n):
        strict = pdom[n] - {n}
        if EXIT not in pdom[n]:
            return EXIT                       # never reaches the end: no post-dominator
        for d in strict:
            if len(pdom[d]) == len(strict): return d
        return EXIT
    return dom, ipdom


def main():
    bad = []
    rng = random.Random(7)
    for k in range(300):
        ins = program(rng, rng.randrange(3, 40))
        addr2idx = {pc: i for i, (_, _, pc) in enumerate(ins)}
        g = gen_cfg.Graph(ins, addr2idx)
        dom, ipdom = reference(g)
        for n in g.nodes:
            for d in g.nodes:
                if (d in dom[n]) != (d in g.dom[n]):
                    bad.append('same: function %d node %d: %d dominates it %s, the tree says %s' % (k, n, d, d in dom[n], d in g.dom[n]))
            if ipdom(n) != g.ipdom(n):
                bad.append('same: function %d node %d: ipdom %d, the tree says %d' % (k, n, ipdom(n), g.ipdom(n)))
        if len(bad) > 8: break
    ins = program(random.Random(3), 10000)
    t = time.time()
    gen_cfg.Graph(ins, {pc: i for i, (_, _, pc) in enumerate(ins)})
    if time.time() - t > 10:
        bad.append('big: 10,000 instructions took %.1f s' % (time.time() - t))
    rng = random.Random(11)
    for k in range(50):
        ins = program(rng, rng.randrange(3, 60))
        g = gen_cfg.Graph(ins, {pc: i for i, (_, _, pc) in enumerate(ins)})
        for n in g.nodes:
            seen, todo = set(), [n]
            while todo:
                x = todo.pop()
                if x in seen or x == EXIT: continue
                seen.add(x); todo.extend(g.succ[x])
            if set(g.reach(n)) != seen or set(g.reach(n)) != seen:          # twice: a cached answer is the same answer
                bad.append('reach: function %d node %d' % (k, n)); break
        for _ in range(3):                                                 # the first common nodes, against the pairwise rule
            common = set(rng.sample(g.nodes, min(len(g.nodes), rng.randrange(1, 8))))
            want = sorted(x for x in common if not any(y != x and x in g.reach(y) and y not in g.reach(x) for y in common))
            if sorted(g._firsts(common)) != want:
                bad.append('reach: firsts in function %d: %s, want %s' % (k, sorted(g._firsts(common)), want))
    ins = program(random.Random(5), 3000)
    g = gen_cfg.Graph(ins, {pc: i for i, (_, _, pc) in enumerate(ins)})
    t2 = time.time()
    for n in g.nodes:
        if len([s for s in g.succ[n] if s != EXIT]) == 2:
            g.ijoin(n)
    if time.time() - t2 > 20:
        bad.append('reach: ijoin over a 3,000-instruction function took %.1f s' % (time.time() - t2))
    if bad:
        sys.exit('[ERROR] cfgdom check failed:\n' + '\n'.join(bad[:10]))
    print('[cfgdom] ok: dominator trees give the set equations\' answers; 10,000 instructions in %.1f s' % (time.time() - t))


if __name__ == '__main__':
    main()
