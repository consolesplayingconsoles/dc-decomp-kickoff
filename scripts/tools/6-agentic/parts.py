#!/usr/bin/env python3
"""parts.py: an outlier function (far larger than the rest, a timeout on its own) read in parts. Run in the repo. Stdlib only.

    python3 tools/6-agentic/parts.py map  <function> [--max N]     the parts, from its control flow: state/parts/<function>/parts.txt
    python3 tools/6-agentic/parts.py read <function>               each part read by the generator: state/parts/<function>/<part>.c

A whole run of such a function blocks the machine for hours and ends in a timeout, so it is never given a longer limit. map cuts it
along its own structure: the dominator tree of its control flow (gen_cfg._idom). A block that dominates a region is entered only
through its first instruction, so the region is a part: map descends through chains with one big child and cuts where a block has
several big ones, until every part has at most --max instructions (default 600). Long jumps (`jmp @rN` through a pool word) to one
place are the sections' shared exit; a branch out of the function goes there too. What dominates no big region (the head, the glue
between parts) is listed as glue.

read makes a scratch copy of the repo under state/parts/<function>/repo (links to the executable and the tools, its own
functions.txt): the function's entry keeps its name and its range up to the first part, every part becomes an entry
part_<address> up to the next part, and the shared exit one more. The generator reads each part as a small function: a branch to the
next part or to the exit is a tail jump. Every address one part branches to inside another starts a part of its own (cut_points): the
reader refuses a branch into the middle of an entry. What a part receives from the parts before it shows in its C: the words of the parent's frame
as stack parameters (a8 ...), the callee-saved registers as temporaries read before they are set. Nothing is checked or written to
src/: the parts' C is the material for the join, which is done by hand (SKILL.md step 6, "An outlier function is done in parts"):
one function, one frame, the parts in order, then proven on drawn and directed cases.
"""
import os as _tp_os, sys as _tp_sys  # noqa: E401  every tools folder on the import path (tools/toolpath.py)
_tp_sys.path.insert(0, _tp_os.path.normpath(_tp_os.path.join(_tp_os.path.dirname(_tp_os.path.abspath(__file__)), '..')))
import toolpath  # noqa: E402,F401
import collections
import os
import re
import subprocess
import sys

BRANCH = ('bt', 'bf', 'bt/s', 'bf/s')


def disasm(name):
    """[(address, mnemonic, operands, pool value)] of the function's code (shdis --func), data words left out"""
    out = subprocess.run([sys.executable, 'tools/sim/shdis.py', '--func', name], capture_output=True, text=True).stdout
    code = []
    for l in out.splitlines():
        m = re.match(r'([0-9a-f]{8}) ([0-9a-f]{4,8})\s+(\S+)\s*(.*)', l)
        if not m or m.group(3).startswith('.'):
            continue
        ops, _, note = m.group(4).partition(';')
        pv = re.search(r'=([0-9a-f]{8})', note)
        code.append((int(m.group(1), 16), m.group(3), ops.strip(), int(pv.group(1), 16) if pv else None))
    return code


def graph(code):
    """(successors, the shared exit or None): the control flow by instruction. A `jmp @rN` whose register was loaded from a pool word
    goes to that word's address; when the long jumps all go to one place inside the function, that place is the shared exit"""
    addrs = [a for a, _, _, _ in code]
    idx = {a: i for i, a in enumerate(addrs)}
    jumps = []
    loaded = {}
    for a, mn, ops, pv in code:
        if mn == 'mov.l' and pv is not None and ops.endswith(('r0', 'r1', 'r2', 'r3', 'r4', 'r5', 'r6', 'r7')):
            loaded[ops.split(',')[-1].strip()] = pv
        if mn == 'jmp':
            jumps.append(loaded.get(ops.strip('@ ')))
    inside = [t for t in jumps if t in idx]
    exit_ = inside[0] if inside and all(t == inside[0] for t in inside) else None
    succ = collections.defaultdict(set)
    for i, (a, mn, ops, pv) in enumerate(code):
        nxt = addrs[i + 1] if i + 1 < len(addrs) else None
        t = int(ops.split()[0], 16) if ops.startswith('0x') else None
        if mn == 'bra':
            succ[a].add(t if t in idx else exit_)
        elif mn in BRANCH:
            succ[a].add(t if t in idx else exit_)
            succ[a].add(addrs[i + 2] if mn.endswith('/s') and i + 2 < len(addrs) else nxt)
        elif mn == 'jmp':
            succ[a].add(exit_)
        elif mn in ('rts', 'rte'):
            pass
        elif nxt is not None:
            succ[a].add(nxt)
    for a in addrs:
        succ[a].discard(None)
    return succ, exit_


def parts(code, maxn=600, limit=None):
    """[(kind, address, instructions)]: 'part' regions of at most maxn instructions (each dominated by its first instruction), and
    'glue' for what the cut leaves (the head, the blocks between parts), in address order"""
    import gen_cfg
    addrs = [a for a, _, _, _ in code]
    succ, exit_ = graph(code)
    pred = collections.defaultdict(set)
    for a, ts in succ.items():
        for t in ts:
            pred[t].add(a)
    root = addrs[0]
    idom = gen_cfg._idom(set(addrs), root, {a: list(succ[a]) for a in addrs}, {a: list(pred[a]) for a in addrs})
    kids = collections.defaultdict(list)
    for n, d in idom.items():
        if n != d:
            kids[d].append(n)
    size = {}

    def count(n):
        if n not in size:
            st, c = [n], 0
            while st:
                x = st.pop()
                c += 1
                st += kids[x]
            size[n] = c
        return size[n]
    limit = limit if limit is not None else max(20, maxn // 10)
    out = []

    def cut(n):
        if count(n) <= maxn:
            out.append(('part', n, count(n)))
            return
        while True:
            big = [c for c in kids[n] if count(c) >= limit and c != exit_]
            if len(big) == 1 and count(big[0]) > maxn:
                n = big[0]
                continue
            break
        out.append(('glue', n, count(n) - sum(count(c) for c in big)))
        for c in big:
            cut(c)
    cut(root)
    if exit_ is not None:
        out.append(('exit', exit_, count(exit_)))
    return sorted(out, key=lambda x: x[1])


def write_map(name, maxn):
    code = disasm(name)
    if not code:
        sys.exit('[ERROR] %s: no code (is it in functions.txt?)' % name)
    ps = parts(code, maxn)
    d = os.path.join('state', 'parts', name)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'parts.txt'), 'w') as f:
        f.write('# %s in parts (tools/6-agentic/parts.py map): kind address instructions\n' % name)
        for k, a, n in ps:
            f.write('%s %08x %d\n' % (k, a, n))
    for k, a, n in ps:
        print('%-4s %08x %5d instructions' % (k, a, n))
    print('%d parts, %d glue: %s' % (sum(1 for p in ps if p[0] == 'part'), sum(1 for p in ps if p[0] == 'glue'), os.path.join(d, 'parts.txt')))


def scratch_functions(lines, name, cuts):
    """functions.txt lines with `name` split at the cut addresses: the entry keeps its name up to the first cut, each cut becomes
    part_<address> up to the next cut, the last one up to the function's end"""
    out = []
    for l in lines:
        p = l.split()
        if len(p) >= 4 and p[0] == 'F' and p[3] == name:
            a, sz = int(p[1], 16), int(p[2])
            pts = sorted(c for c in set(cuts) if a < c < a + sz)
            bounds = [a] + pts + [a + sz]
            for i in range(len(bounds) - 1):
                out.append('F %08x %d %s' % (bounds[i], bounds[i + 1] - bounds[i], name if i == 0 else 'part_%08x' % bounds[i]))
        else:
            out.append(l)
    return out


def cut_points(code, cuts):
    """the cuts, closed under the branches between chunks: an address another chunk branches to starts a chunk of its own (the reader
    refuses a branch into the middle of another entry)"""
    import bisect
    cuts = set(cuts) | {code[0][0]}
    while True:
        cs = sorted(cuts)
        chunk = lambda a: cs[bisect.bisect_right(cs, a) - 1]
        new = set()
        for a, mn, ops, pv in code:
            if mn in ('bra', 'bsr') + BRANCH and ops.startswith('0x'):
                t = int(ops.split()[0], 16)
                if code[0][0] <= t <= code[-1][0] and t not in cuts and chunk(t) != chunk(a):
                    new.add(t)
        if not new:
            return sorted(cuts - {code[0][0]})
        cuts |= new


def read(name):
    d = os.path.join('state', 'parts', name)
    pf = os.path.join(d, 'parts.txt')
    if not os.path.exists(pf):
        sys.exit('[ERROR] run `parts.py map %s` first' % name)
    cuts = [int(l.split()[1], 16) for l in open(pf) if l[:1] != '#']
    cuts = cut_points(disasm(name), cuts)
    repo = os.path.join(d, 'repo')
    os.makedirs(os.path.join(repo, 'src'), exist_ok=True)
    os.makedirs(os.path.join(repo, 'state'), exist_ok=True)
    for f in ('1ST_READ.BIN', 'BASE', 'tools', 'globals.txt', 'symbols.txt', 'layout.txt', 'sdk.txt', 'sdk-source'):
        dst = os.path.join(repo, f)
        if os.path.exists(f) and not os.path.lexists(dst):
            os.symlink(os.path.abspath(f), dst)
    lines = open('functions.txt').read().split('\n')
    open(os.path.join(repo, 'functions.txt'), 'w').write('\n'.join(scratch_functions(lines, name, cuts)))
    names = [name] + ['part_%08x' % c for c in sorted(cuts)]
    script = ("import sys; sys.path.insert(0, 'tools'); sys.path.insert(0, 'tools/5-generated/gen_equiv')\n"
              "import toolpath, gen_core, gen_drv, gen_pipe\n"
              "n = sys.argv[1]\n"
              "try:\n"
              "    v = gen_pipe.variants(n, False)\n"
              "    src, c = gen_drv.build(n, v[0], False)\n"
              "    print(src)\n"
              "except gen_core.Skip as e:\n"
              "    print('/* not read: %s */' % e)\n")
    for n in names:
        r = subprocess.run([sys.executable, '-c', script, n], cwd=repo, capture_output=True, text=True, timeout=1800)
        text = r.stdout if r.stdout.strip() else '/* not read: %s */\n' % (r.stderr.strip().splitlines() or ['no output'])[-1]
        open(os.path.join(d, n + '.c'), 'w').write(text)
        first = text.strip().splitlines()[0] if text.strip() else ''
        print('%-24s %s' % (n, 'not read' if first.startswith('/* not read') else '%d lines' % len(text.splitlines())))
    print('the parts\' C is in %s: join them by hand (SKILL.md step 6)' % d)


def main(argv):
    if len(argv) < 2 or argv[0] not in ('map', 'read'):
        sys.exit(__doc__)
    maxn = int(argv[argv.index('--max') + 1]) if '--max' in argv else 600
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '5-generated', 'gen_equiv'))
    if argv[0] == 'map':
        write_map(argv[1], maxn)
    else:
        read(argv[1])


if __name__ == '__main__':
    main(sys.argv[1:])
