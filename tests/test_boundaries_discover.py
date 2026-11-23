#!/usr/bin/env python3
"""boundaries.py --discover: the candidates a list of entries leaves out (scripts/tools/common/boundaries.py). No game data, no compiler.
Stdlib only.

boundaries.py judges the addresses a candidates file names; nothing used to name them. Power Stone 2 0C0B819E is a 42-byte function in the
gap after the 34-byte FUN_0c0b817c, reached by two `bra` of FUN_0c0b857c (a tail jump into a function the list does not have): the generator
could not call it, wrote the four functions it jumps to inline (1,200 of 1,562 bytes), and the proof differed from the original (one call
against several). --discover walks every listed entry and names each address in a gap (inside no listed range) that its code jumps or
calls to.

    check.py      a temp repo: listed f1, f2 and the callers; unlisted routines in the gaps:
                    bra      a listed function's `bra` back to an unlisted routine (the tail jump): a candidate
                    bsr      a `bsr` to one: a candidate
                    pool     a `jsr @r1` with r1 loaded from a pool word that holds its address: a candidate
                    data     a pool word with an address that is only read through (mov.l @r1,r0), never called or jumped to: not a candidate
                    none     an unlisted routine nothing refers to: not a candidate
                    listed   a `bra` to a listed entry, and one into the middle of a listed function: not candidates
                  and the three candidates, given to boundaries.py as a candidates file: each one "function"
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
PUSH_PR, POP_PR = 0x4F22, 0x4F26


def w(*ws):
    return b''.join(struct.pack('<H', x) for x in ws)


def bra_to(at, target):
    return 0xA000 | (((target - (at + 4)) // 2) & 0xFFF)


def bsr_to(at, target):
    return 0xB000 | (((target - (at + 4)) // 2) & 0xFFF)


class TestBoundariesDiscover(unittest.TestCase):
    def setUp(self):
        self.addCleanup(os.chdir, os.getcwd())
        saved_path = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        environ = mock.patch.dict(os.environ)
        environ.start()
        self.addCleanup(environ.stop)

    def test_boundaries_discover(self):
        code, listed, at = b'', [], {}

        def put(name, data, is_listed, align=2):
            nonlocal code
            while (BASE + len(code)) % align:
                code += w(0)
            at[name] = BASE + len(code)
            code += data
            if is_listed:
                listed.append((name, at[name], len(data)))

        routine = w(PUSH_PR, POP_PR, RTS, NOP)             # an unlisted routine: push pr, pop pr, return
        put('f1', w(RTS, NOP), True)
        put('g_bra', routine, False)
        put('f2', w(RTS, NOP), True)
        put('g_bsr', routine, False)
        put('g_pool', routine, False)
        put('g_none', routine, False)
        put('g_data', routine, False)
        # a: a tail bra back to g_bra.  b: a bsr to g_bsr, then a return.  k: a bra to f2's entry, and one into the middle of f2
        put('a', w(bra_to(BASE + len(code), at['g_bra']), NOP), True)
        put('b', w(bsr_to(BASE + len(code), at['g_bsr']), NOP, RTS, NOP), True)
        put('k', w(bra_to(BASE + len(code), at['f2']), NOP, bra_to(BASE + len(code) + 4, at['f2'] + 2), NOP), True)
        # p: mov.l @(2,pc),r1 / jsr @r1 / nop / rts / nop / pad / .long g_pool    (4-aligned, the pool 12 bytes on)
        p_at = BASE + len(code)
        p_at += (-p_at) % 4
        put('p', w(0xD102, 0x410B, NOP, RTS, NOP, 0) + struct.pack('<I', at['g_pool']), True, align=4)
        # q: the same load, but r1 is only read through: mov.l @r1,r0 / rts / nop    (the pool holds g_data's address)
        put('q', w(0xD101, 0x6012, RTS, NOP) + struct.pack('<I', at['g_data']), True, align=4)
        tmp = tempfile.mkdtemp(prefix='boundaries_discover_')
        try:
            shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
            open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
            open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
            open(os.path.join(tmp, 'functions.txt'), 'w').write(''.join('F %08x %d %s\n' % (a, s, n) for n, a, s in listed))
            r = subprocess.run([sys.executable, 'tools/common/boundaries.py', '--discover'], cwd=tmp, capture_output=True, text=True, timeout=120)
            out = r.stdout + r.stderr
            found = set()
            for line in r.stdout.splitlines():
                p = line.split('#')[0].split()
                if p:
                    found.add(int(p[0], 16) & 0x1FFFFFFF)
            want = {at[n] & 0x1FFFFFFF for n in ('g_bra', 'g_bsr', 'g_pool')}
            for n in ('g_bra', 'g_bsr', 'g_pool'):
                assert at[n] & 0x1FFFFFFF in found, '%s, reached by a %s, is not a candidate:\n%s' % (n, n[2:], out)
            for n in ('g_none', 'g_data'):
                assert at[n] & 0x1FFFFFFF not in found, '%s is a candidate, though nothing jumps or calls to it:\n%s' % (n, out)
            for n in ('f1', 'f2', 'k'):
                assert at[n] & 0x1FFFFFFF not in found, 'the listed %s is a candidate:\n%s' % (n, out)
            assert (at['f2'] + 2) & 0x1FFFFFFF not in found, 'the middle of the listed f2 is a candidate:\n%s' % out
            assert found == want, 'candidates %s, wanted %s:\n%s' % (sorted(hex(x) for x in found), sorted(hex(x) for x in want), out)
            open(os.path.join(tmp, 'cands.txt'), 'w').write(r.stdout)
            r2 = subprocess.run([sys.executable, 'tools/common/boundaries.py', 'cands.txt'], cwd=tmp, capture_output=True, text=True, timeout=120)
            rows = [l for l in r2.stdout.splitlines() if l[:8].strip() and len(l.split()[0]) == 8]
            assert len(rows) == 3 and all(' function ' in l and 'not a function' not in l for l in rows), \
                'boundaries.py does not accept the three discovered candidates as functions:\n%s' % r2.stdout
            print('[boundaries_discover] ok: a bra, a bsr and a jsr through a pool word into a gap are candidates; a data pointer, an unreferenced routine and listed entries are not')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
