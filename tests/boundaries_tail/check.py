#!/usr/bin/env python3
"""A function that ends with a forward `bra` to another listed function is a function (scripts/tools/boundaries.py, reach(tails=)).
The bra is a tail jump into that function, not more of this one. Zombie Revenge 0C04179C ends with `bra FUN_0c041f2a`, a function after it:
the walk followed it, ran into that entry, and seven hidden functions the C calls stayed unlisted; the build ran data copies of them.
No game data, no compiler. Stdlib only.

    check.py      a temp repo: f1, a gap holding g (push pr, a bf over a bra, pop, rts on one path and `bra f2` on the other), then f2:
                    g          "function", its size covers both paths
                  and a piece that really runs on into f2 (no return, no branch), still refused:
                    fall       "not a function"
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
BASE = 0x8C010000
NOP, RTS = 0x0009, 0x000B


def w(*ws):
    return b''.join(struct.pack('<H', x) for x in ws)


def bra_to(at, target):
    return 0xA000 | (((target - (at + 4)) // 2) & 0xFFF)


def main():
    f1 = w(RTS, NOP)
    g_at = BASE + len(f1)
    # g: sts.l pr,@-r15 / tst r4,r4 / bf +4 / lds.l @r15+,pr / bra f2 / nop / lds.l @r15+,pr / rts / nop
    g_words = [0x4F22, 0x2448, 0x8B02, 0x4F26, None, NOP, 0x4F26, RTS, NOP]
    fall_at = g_at + 2 * len(g_words)
    fall = w(0x7001, 0x7001)                     # add #1,r0 twice, then f2 itself: no return of its own
    f2_at = fall_at + len(fall)
    g_words[4] = bra_to(g_at + 8, f2_at)
    code = f1 + w(*g_words) + fall + w(RTS, NOP)
    tmp = tempfile.mkdtemp(prefix='boundaries_tail_')
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d f1\nF %08x 4 f2\n' % (BASE, len(f1), f2_at))
        open(os.path.join(tmp, 'cands.txt'), 'w').write('%08x\n%08x\n' % (g_at, fall_at))
        r = subprocess.run([sys.executable, 'tools/boundaries.py', 'cands.txt'], cwd=tmp, capture_output=True, text=True, timeout=120)
        out = r.stdout + r.stderr
        by = {}
        for line in out.splitlines():
            p = line.split()
            if p and len(p[0]) == 8:
                try:
                    by[int(p[0], 16) & 0x1FFFFFFF] = line
                except ValueError:
                    pass
        g_line, fall_line = by.get(g_at & 0x1FFFFFFF, ''), by.get(fall_at & 0x1FFFFFFF, '')
        assert ' function ' in g_line and 'size %d' % (2 * len(g_words)) in g_line, \
            'g, which ends with a tail bra to f2, is not a function of %d bytes: %r\n%s' % (2 * len(g_words), g_line, out)
        assert 'not a function' in fall_line, 'a piece that runs on into f2 is accepted: %r' % fall_line
        print('[boundaries_tail] ok: a forward bra to another listed function ends a function as a tail jump; running on into one still does not')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


main()
