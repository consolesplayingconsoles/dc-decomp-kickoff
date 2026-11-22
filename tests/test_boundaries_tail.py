#!/usr/bin/env python3
"""A function that ends with a forward `bra` to another listed function is a function (scripts/tools/common/boundaries.py, reach(tails=)).
The bra is a tail jump into that function, not more of this one. Zombie Revenge 0C04179C ends with `bra FUN_0c041f2a`, a function after it:
the walk followed it, ran into that entry, and seven hidden functions the C calls stayed unlisted; the build ran data copies of them.
No game data, no compiler. Stdlib only.

    check.py      a temp repo: f1, a gap holding g (push pr, a bf over a bra, pop, rts on one path and `bra f2` on the other), then f2:
                    g          "function", its size covers both paths
                  and a piece that really runs on into f2 (no return, no branch), still refused:
                    fall       "not a function"
                  after f2: h, whose `bt` goes back to f2's entry (Zombie Revenge 0C086A44 -> FUN_0c08696c): "function";
                  k, whose `bt` goes back into the middle of f2: "not a function"
"""
import unittest
from unittest import mock
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
BASE = 0x8C010000
NOP, RTS = 0x0009, 0x000B


def w(*ws):
    return b''.join(struct.pack('<H', x) for x in ws)


def bra_to(at, target):
    return 0xA000 | (((target - (at + 4)) // 2) & 0xFFF)


class TestBoundariesTail(unittest.TestCase):
    def setUp(self):
        self.addCleanup(os.chdir, os.getcwd())
        saved_path = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        environ = mock.patch.dict(os.environ)
        environ.start()
        self.addCleanup(environ.stop)
        snapshot = self._snapshot_modules()
        self.addCleanup(self._restore_modules, snapshot)

    @staticmethod
    def _snapshot_modules():
        tools = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts')
        modules = dict(sys.modules)
        state = {}
        for name, mod in modules.items():
            if (getattr(mod, '__file__', None) or '').startswith(tools):
                state[name] = dict(vars(mod))
        return modules, state

    @staticmethod
    def _restore_modules(snapshot):
        modules, state = snapshot
        for name in list(sys.modules):
            if name not in modules:
                del sys.modules[name]
        sys.modules.update(modules)
        for name, saved in state.items():
            vars(modules[name]).clear()
            vars(modules[name]).update(saved)

    def test_boundaries_tail(self):
        f1 = w(RTS, NOP)
        g_at = BASE + len(f1)
        # g: sts.l pr,@-r15 / tst r4,r4 / bf +4 / lds.l @r15+,pr / bra f2 / nop / lds.l @r15+,pr / rts / nop
        g_words = [0x4F22, 0x2448, 0x8B02, 0x4F26, None, NOP, 0x4F26, RTS, NOP]
        fall_at = g_at + 2 * len(g_words)
        fall = w(0x7001, 0x7001)                     # add #1,r0 twice, then f2 itself: no return of its own
        f2_at = fall_at + len(fall)
        g_words[4] = bra_to(g_at + 8, f2_at)
        # h, after f2: tst r4,r4 / bt f2 (back to a listed entry: a conditional tail jump) / rts / nop.  k: the same with the bt going
        # back to the middle of f2, which is no entry: still refused
        h_at = f2_at + 4
        k_at = h_at + 8
        bt_to = lambda at, target: 0x8900 | (((target - (at + 4)) // 2) & 0xFF)
        code = f1 + w(*g_words) + fall + w(RTS, NOP) + w(0x2448, bt_to(h_at + 2, f2_at), RTS, NOP) + w(0x2448, bt_to(k_at + 2, f2_at + 2), RTS, NOP)
        # d, after k: data that decodes as `bsr` to the middle of nowhere, then a return: the walk reaches an rts, and it is still no function
        # (Zombie Revenge listed ten tables that way). c calls f1, a listed function, the same way: a function
        d_at = k_at + 8
        c_at = d_at + 8
        bsr_to = lambda at, target: 0xB000 | (((target - (at + 4)) // 2) & 0xFFF)
        code += w(bsr_to(d_at, f2_at + 2), NOP, RTS, NOP) + w(bsr_to(c_at, BASE), NOP, RTS, NOP)
        tmp = tempfile.mkdtemp(prefix='boundaries_tail_')
        try:
            shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
            open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
            open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
            open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d f1\nF %08x 4 f2\n' % (BASE, len(f1), f2_at))
            open(os.path.join(tmp, 'cands.txt'), 'w').write('%08x\n%08x\n%08x\n%08x\n%08x\n%08x\n' % (g_at, fall_at, h_at, k_at, d_at, c_at))
            r = subprocess.run([sys.executable, 'tools/common/boundaries.py', 'cands.txt'], cwd=tmp, capture_output=True, text=True, timeout=120)
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
            h_line, k_line = by.get(h_at & 0x1FFFFFFF, ''), by.get(k_at & 0x1FFFFFFF, '')
            assert ' function ' in h_line and 'not a function' not in h_line and 'size 8' in h_line, 'h, whose bt goes back to the listed f2, is not a function: %r\n%s' % (h_line, out)
            assert 'not a function' in k_line, 'k, whose bt goes back into the middle of f2, is accepted: %r' % k_line
            d_line, c_line = by.get(d_at & 0x1FFFFFFF, ''), by.get(c_at & 0x1FFFFFFF, '')
            assert 'not a function' in d_line, 'd, data whose bsr goes to no function, is accepted: %r\n%s' % (d_line, out)
            assert ' function ' in c_line and 'not a function' not in c_line, 'c, which calls the listed f1 and returns, is refused: %r\n%s' % (c_line, out)
            print('[boundaries_tail] ok: a forward bra to another listed function ends a function as a tail jump; running on into one still does not')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
