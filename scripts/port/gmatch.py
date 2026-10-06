#!/usr/bin/env python3
"""Name Dreamcast globals from a port's data symbols. Stdlib only. See references/port-symbols.md.

    gmatch.py [pairs file, default accepted.tsv]  ->  globals.tsv

For every paired function, the Dreamcast globals it touches and the port globals it touches (as
symbol + offset) are co-observed. A Dreamcast address and a port symbol+offset are paired when
they are each other's best co-occurrence, seen in >= 2 paired functions, in >= 60% of the pairs
using the Dreamcast address and >= 30% of those using the port symbol (ports add uses).
Feed globals.tsv back into match.py (shared neighbours) and repeat until nothing changes.
"""
import collections, sys
from portcfg import load, sym_of, DROP_GLOBALS

dc = {f['e'].lower().rjust(8, '0'): f for f in load('dc_features.jsonl')}
so = {f['e']: f for f in load('port_features.jsonl')}
by_name = collections.defaultdict(list)
for e, f in so.items():
    by_name[f['n']].append(e)

pairs = []
for l in open(sys.argv[1] if len(sys.argv) > 1 else 'accepted.tsv'):
    d, dn, sn, how = l.rstrip('\n').split('\t')
    if d in dc and len(by_name.get(sn, [])) == 1:
        pairs.append((d, by_name[sn][0]))

co = collections.defaultdict(collections.Counter)
nd, ns = collections.Counter(), collections.Counter()
for d, s in pairs:
    A = set(dc[d].get('g', [])) - DROP_GLOBALS
    B = {sym_of(int(x, 16)) for x in so[s].get('g', [])} - {None}
    for a in A: nd[a] += 1
    for b in B: ns[b] += 1
    for a in A:
        for b in B: co[a][b] += 1
best_for_b = {}
for a, c in co.items():
    for b, k in c.items():
        if k > best_for_b.get(b, (0, None))[0]:
            best_for_b[b] = (k, a)
res = []
for a, c in co.items():
    top = c.most_common(2)
    (b, k), second = top[0], (top[1][1] if len(top) > 1 else 0)
    if k >= 2 and k > second and best_for_b[b][1] == a and k / nd[a] >= 0.6 and k / ns[b] >= 0.3:
        res.append((a, b[0], b[1], k, nd[a], ns[b]))
names = collections.Counter(r[1] for r in res)
with open('globals.tsv', 'w') as out:
    out.write('# dc_addr\tport_symbol\toffset\tseen_together\tdc_seen\tport_seen\n')
    for a, n, off, k, x, y in sorted(res):
        if names[n] == 1:                       # a name claimed by two addresses: neither is sure
            out.write('%s\t%s\t%d\t%d\t%d\t%d\n' % (a, n, off, k, x, y))
print('%d globals from %d function pairs' % (sum(1 for r in res if names[r[1]] == 1), len(pairs)))
