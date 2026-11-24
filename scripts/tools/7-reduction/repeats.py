#!/usr/bin/env python3
"""repeats.py: the game functions whose ORIGINAL code repeats one run of instructions many times: the ones a person can write as a
loop, far below the original's size. Run in the repo. Stdlib only.

    python3 tools/7-reduction/repeats.py [--min-c BYTES] [--share S] [--window N] [--all]

The excess of a function's C over its original says nothing about how small a person can make it: an original built without
optimisation, or with a loop unrolled by hand or by the compiler, holds the same run of instructions many times, and C written as
one loop comes out well under the original's size (two functions written so: 9,064 bytes of C to 370, original 3,394; 5,504 to
1,894, original 4,504). Their originals had 93% and 66% of their instructions in runs repeated elsewhere in the function.

Each instruction is reduced to its shape (registers and numbers masked), and every run of N instructions (--window, 10) that occurs
twice or more in the function marks its instructions as repeated. Lists the functions the console build compiles (layout.txt's
`game` region outside `keep`) with at least S of their instructions repeated (--share, 0.5) and at least BYTES of C (--min-c, 1500,
from build/sizes.json; the original's size where there is no entry), largest C times share first. Functions written by hand
(a `/* manual: */` comment naming them) are left out unless --all. Hand the ones it lists to `PROMPT_handshrink.md`.
"""
import os as _tp_os, sys as _tp_sys  # noqa: E401  every tools folder on the import path (tools/toolpath.py)
_tp_sys.path.insert(0, _tp_os.path.normpath(_tp_os.path.join(_tp_os.path.dirname(_tp_os.path.abspath(__file__)), '..')))
import toolpath  # noqa: E402,F401
import collections
import json
import os
import re
import struct
import sys

import layout  # noqa: E402
import shdis  # noqa: E402


def shape(text):
    """An instruction's text with its registers and numbers masked: two copies of one run compare equal."""
    t = text.split(';')[0]
    t = re.sub(r'0x[0-9a-fA-F]+|#-?\d+|\b\d+\b', 'K', t)
    t = re.sub(r'\bf?r\d+\b', 'R', t)
    return t.strip()


def repeated_share(words, base, window=10):
    """(share of instructions in a run of `window` that occurs twice or more, most copies of one run) for one function's words."""
    tx = []
    for i, w in enumerate(words):
        d = shdis.decode(w, base + 2 * i)
        tx.append(shape(d if isinstance(d, str) else d[0]))
    n = len(tx)
    if n < 2 * window:
        return 0.0, 0
    seen = collections.defaultdict(list)
    for i in range(n - window + 1):
        seen[tuple(tx[i:i + window])].append(i)
    cov = [0] * n
    most = 0
    for pos in seen.values():
        if len(pos) >= 2:
            most = max(most, len(pos))
            for p in pos:
                for j in range(p, p + window):
                    cov[j] = 1
    return sum(cov) / n, most


def manual():
    """Names a `/* manual: ... */` comment in the C names, or that it stands right above."""
    out = set()
    for f in layout.c_files():
        t = open(f, errors='replace').read()
        for m in re.finditer(r'/\*\s*manual:(.*?)\*/', t, re.S):
            out |= set(re.findall(r'\b(FUN_[0-9a-fA-F]+|\w+)\b', m.group(1)))
            h = re.match(r'\s*\n[A-Za-z_][\w \t\*]*?\b(\w+)\s*\(', t[m.end():])
            if h:
                out.add(h.group(1))
    return out


def main(argv):
    opt = lambda k, d: type(d)(argv[argv.index(k) + 1]) if k in argv else d
    min_c, share, window = opt('--min-c', 1500), opt('--share', 0.5), opt('--window', 10)
    exe = open('1ST_READ.BIN', 'rb').read()
    base = int(open('BASE').read().split()[0], 16)
    sizes = {}
    if os.path.exists(os.path.join('build', 'sizes.json')):
        sizes = {n: c for n, o, c in json.load(open(os.path.join('build', 'sizes.json')))}
    skip = set() if '--all' in argv else manual()
    rows = []
    for line in open('functions.txt'):
        p = line.split()
        if len(p) < 4 or p[0] != 'F':
            continue
        a, s, name = int(p[1], 16), int(p[2]), p[3]
        if s < 2 * window * 2 or name in skip or not layout.moving(a):
            continue
        c = sizes.get(name) or s
        if c < min_c:
            continue
        words = struct.unpack_from('<%dH' % (s // 2), exe, a - base)
        sh, most = repeated_share(words, a, window)
        if sh >= share:
            rows.append((c * sh, name, s, c, sh, most))
    rows.sort(reverse=True)
    print('%-22s %8s %8s %9s %7s' % ('function', 'original', 'C', 'repeated', 'copies'))
    for _, name, s, c, sh, most in rows:
        print('%-22s %8d %8d %8.0f%% %7d' % (name, s, c, 100 * sh, most))
    print('%d function(s)' % len(rows))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
