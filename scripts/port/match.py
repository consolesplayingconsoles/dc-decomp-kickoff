#!/usr/bin/env python3
"""Pair Dreamcast functions with a port's named ones. Stdlib only. See references/port-symbols.md.

    match.py            (settings in the environment, see portcfg.py)  ->  pairs.tsv

1. Seeds: seeds.tsv (optional, "dc_addr<TAB>port_name", pairs proven by reading code), names both
   sides already share, strings only one function uses on each side, rare shared constants.
2. Propagation: callees between two already-paired calls; a paired function's only unpaired callers;
   shared paired neighbours (callers, callees, paired globals from globals.tsv, rare constants),
   with code size as a tie-break. Repeats until nothing new.
3. Conflicts (one function claimed twice) are dropped, never guessed.
pairs.tsv: dc_addr  dc_name  port_name  how
"""
import collections, math, os, statistics
from portcfg import load, dc_names, FUNC_SYMS, is_original, demangle, runtime_helper, DROP_GLOBALS, sym_of

dc = {f['e'].lower().rjust(8, '0'): f for f in load('dc_features.jsonl')}
so = {f['e']: f for f in load('port_features.jsonl')}
names = dc_names()

pairs, back, how = {}, {}, {}
bad_dc, bad_so = set(), set()

def add(d, s, why):
    if d in bad_dc or s in bad_so or pairs.get(d) == s:
        return False
    if d in pairs or s in back:
        for x in (d, back.get(s)):
            if x and x in pairs:
                del back[pairs[x]]; del pairs[x]; how.pop(x, None)
        bad_dc.add(d); bad_so.add(s)
        return False
    pairs[d] = s; back[s] = d; how[d] = why
    return True

by_name = collections.defaultdict(list)
for e, f in so.items():
    by_name[f['n']].append(e)

# 0. proven seeds
if os.path.exists('seeds.tsv'):
    for l in open('seeds.tsv'):
        if l.strip() and not l.startswith('#'):
            d, n = l.split()[:2]
            if len(by_name.get(n, [])) == 1:
                add(d.lower(), by_name[n][0], 'seed')
# 1a. same names
for d, n in names.items():
    if d in dc and not n.startswith(('FUN_', 'thunk_')) and len(by_name.get(n, [])) == 1:
        add(d, by_name[n][0], 'name')
# 1b. strings only one function uses on each side
dstr = collections.defaultdict(set); sstr = collections.defaultdict(set)
for d, f in dc.items():
    for s in f['s']:
        if len(s) >= 5: dstr[s.strip().lower()].add(d)
for e, f in so.items():
    for s in f['s']:
        if len(s) >= 5: sstr[s.strip().lower()].add(e)
for s, ds in dstr.items():
    ss = sstr.get(s)
    if ss and len(ds) == 1 and len(ss) == 1:
        add(next(iter(ds)), next(iter(ss)), 'string %r' % s[:40])
# 1c. rare constants: two shared, each other's only candidate
def kset(f, side):
    out = set()
    for v in f['k']:
        if v < 0x100 or v >= 0xffff0000:
            continue
        if side == 'dc' and (v >> 24) in (0x0c, 0x8c, 0xac):           # Dreamcast addresses
            continue
        if side == 'so' and 0x100000 <= v < 0x4000000:                  # port addresses
            continue
        out.add(v)
    return out
dk = {d: kset(f, 'dc') for d, f in dc.items()}
sk = {e: kset(f, 'so') for e, f in so.items()}
dcnt = collections.Counter(v for ks in dk.values() for v in ks)
scnt = collections.Counter(v for ks in sk.values() for v in ks)
sby = collections.defaultdict(set)
for e, ks in sk.items():
    for v in ks:
        if scnt[v] <= 3: sby[v].add(e)
cand = collections.defaultdict(collections.Counter)
for d, ks in dk.items():
    for v in ks:
        if dcnt[v] <= 3:
            for e in sby.get(v, ()): cand[d][e] += 1
best = {}
for d, c in cand.items():
    top = c.most_common(2)
    if top[0][1] >= 2 and (len(top) == 1 or top[1][1] < top[0][1]):
        best[d] = top[0][0]
rev = collections.Counter(best.values())
for d, e in best.items():
    if rev[e] == 1:
        add(d, e, 'consts')

# 2. propagation
def so_game(e):
    return is_original(FUNC_SYMS.get(e))
def dc_game(a):
    return not runtime_helper(a) or not names.get(a, 'FUN_').startswith('FUN_')
def calls(f, side):
    out = []
    for c in f['c']:
        c = c.lower().rjust(8, '0') if side == 'dc' else c
        ok = (c in dc and dc_game(c)) if side == 'dc' else (c in so and so_game(c))
        if ok and (not out or out[-1] != c):
            out.append(c)
    return out
dcallers = collections.defaultdict(set); scallers = collections.defaultdict(set)
for d, f in dc.items():
    for c in calls(f, 'dc'): dcallers[c].add(d)
for e, f in so.items():
    if so_game(e):
        for c in calls(f, 'so'): scallers[c].add(e)
ratios = [so[s]['sz'] / max(dc[d]['sz'], 1) for d, s in pairs.items() if dc[d]['sz'] > 16]
RATIO = statistics.median(ratios) if ratios else 1.5
def size_ok(x, y, lo=0.4, hi=5):
    return lo <= so[y]['sz'] / max(dc[x]['sz'], 1) / RATIO * 1.5 <= hi

changed, rounds = True, 0
while changed and rounds < 50:
    changed = False; rounds += 1
    for d, s in list(pairs.items()):
        if d not in pairs: continue
        ud = [x for x in dcallers.get(d, ()) if x not in pairs and x not in bad_dc]
        us = [y for y in scallers.get(s, ()) if y not in back and y not in bad_so]
        if len(ud) == 1 and len(us) == 1 and len(dcallers[d]) == len(scallers[s]) and size_ok(ud[0], us[0]):
            changed |= add(ud[0], us[0], 'caller of %s' % names.get(d, d))
    for d, s in list(pairs.items()):
        if d not in pairs: continue
        a, b = calls(dc[d], 'dc'), calls(so[s], 'so')
        anchors, j = [(-1, -1)], 0
        for i, x in enumerate(a):
            if x in pairs and pairs[x] in b[j:]:
                k = b.index(pairs[x], j); anchors.append((i, k)); j = k + 1
        anchors.append((len(a), len(b)))
        for (i0, k0), (i1, k1) in zip(anchors, anchors[1:]):
            ga, gb = a[i0 + 1:i1], b[k0 + 1:k1]
            if len(ga) == len(gb) and 0 < len(ga) <= 8:
                for x, y in zip(ga, gb):
                    if size_ok(x, y):
                        changed |= add(x, y, 'via %s' % names.get(d, d))

# 3. shared neighbours (paired calls, paired globals, rare constants)
gpair = {}
if os.path.exists('globals.tsv'):
    for l in open('globals.tsv'):
        if l.startswith('#') or '\t' not in l: continue
        a, n, off = l.split('\t')[:3]
        if a not in DROP_GLOBALS: gpair[a] = 'G:%s+%s' % (n, off)
GSO = {e: {'G:%s+%s' % r for r in (sym_of(int(x, 16)) for x in f.get('g', [])) if r} for e, f in so.items()} if gpair else {}
RARE = {v for v in set(dcnt) & set(scnt) if dcnt[v] <= 6 and scnt[v] <= 6}
dcallees = {d: set(calls(f, 'dc')) for d, f in dc.items()}
scallees = {e: set(calls(f, 'so')) for e, f in so.items() if so_game(e)}
def dn(x):
    return ({pairs[c] for c in dcallees.get(x, set()) | dcallers.get(x, set()) if c in pairs}
            | {gpair[a] for a in dc[x].get('g', []) if a in gpair} | {'K%d' % v for v in dk[x] & RARE})
def sn(y):
    return ({c for c in scallees.get(y, set()) | scallers.get(y, set()) if c in back}
            | (GSO.get(y, set()) & set(gpair.values())) | {'K%d' % v for v in sk.get(y, set()) & RARE})
def pen(x, y):
    return abs(math.log((so[y]['sz'] / max(dc[x]['sz'], 1)) / RATIO))
for rnd in range(30):
    by_nb, cache = collections.defaultdict(set), {}
    for y in scallees:
        if y in back or y in bad_so: continue
        cache[y] = sn(y)
        for c in cache[y]: by_nb[c].add(y)
    best = {}
    for x in dc:
        if x in pairs or x in bad_dc: continue
        nx = dn(x)
        if len(nx) < 3 or len(dcallers.get(x, ())) > 30:      # busy utilities need direct evidence
            continue
        cnt = collections.Counter(y for c in nx for y in by_nb.get(c, ()))
        sc = sorted(((k / len(nx | cache[y]) - 0.25 * pen(x, y), k, y) for y, k in cnt.items()
                     if k >= 3 and k / len(nx | cache[y]) >= 0.5 and pen(x, y) <= 1.2), reverse=True)
        if sc and (len(sc) == 1 or sc[1][0] < sc[0][0] - 0.15):
            best[x] = (sc[0][2], sc[0][0])
    rv = collections.defaultdict(list)
    for x, (y, j) in best.items(): rv[y].append((j, x))
    new = 0
    for y, xs in rv.items():
        xs.sort(reverse=True)
        if len(xs) == 1 or xs[1][0] < xs[0][0] - 0.15:
            new += add(xs[0][1], y, 'neighbours %.2f' % xs[0][0])
    if not new: break

for d in [d for d in pairs if so[pairs[d]]['n'].startswith(('FUN_', 'thunk_FUN_'))]:
    del back[pairs[d]]; del pairs[d]; how.pop(d, None)
with open('pairs.tsv', 'w') as out:
    for d in sorted(pairs):
        out.write('%s\t%s\t%s\t%s\n' % (d, names.get(d, '?'), so[pairs[d]]['n'], how[d]))
reasons = collections.Counter(h.split()[0] for h in how.values())
print('pairs: %d (%s), conflicts dropped: %d; size ratio port/Dreamcast %.2f'
      % (len(pairs), dict(reasons), len(bad_dc), RATIO))
