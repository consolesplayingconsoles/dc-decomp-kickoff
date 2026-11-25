#!/usr/bin/env python3
"""SHC's division sequence read by the generator (scripts/tools/5-generated/gen_equiv/gen_core.py: div0u, div0s, div1). No game data,
no compiler. Stdlib only.

A division is `div0u` (or `div0s`), then 32 pairs `rotcl X; div1 D,R`, then the fix-ups the sign needs. The generator had no rule
for `div0u`, `div0s` and `div1` and stopped on the first one, so every library division routine (unsigned and signed quotient and
remainder, written by the SDK's C library and by the compiler's runtime) and every division the compiler inlined stayed unread. The
divide step is modelled on the architecture's registers: M and Q are variables the C keeps, T the quotient bit; a run of identical pairs is
one loop in the C (32 unrolled copies are 32 times the text and compile to 32 times the code). The C has no declaration after a statement
(SHC refuses them: error 2500 on every line).

    check.py      a temp repo, each function written by gen_drv.build:
                    unsigned  `div0u`, 32 x (rotcl r0; div1 r1,r2), rotcl r0: written, the steps in one loop
                    signed    `div0s r1,r2`, the same run: written, the steps in one loop
                    short     `div0u` and 3 pairs: written (a run under four pairs is not a loop)
                    lone      `div1` with no `div0u` or `div0s` before it: not written, "div1 without div0"
                    model     the quotient bit rule the C uses, Q = (carry) ^ Q ^ M, equals the simulator's div1 on 20,000 random steps
"""
import unittest
import os
import random
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
TOOLS = os.path.join(SKILL, 'scripts', 'tools')
BASE = 0x0C010000
ROTCL_R0, DIV1_R1_R2, XOR_R2, DIV0U, DIV0S_R1_R2, RTS, NOP = 0x4024, 0x3214, 0x222A, 0x0019, 0x2217, 0x000B, 0x0009
MOV_R4_R0, MOV_R5_R1 = 0x6043, 0x6153


def run(n):
    return [w for _ in range(n) for w in (ROTCL_R0, DIV1_R1_R2)]


FUNCS = {'fudiv': [MOV_R4_R0, MOV_R5_R1, XOR_R2, DIV0U] + run(32) + [ROTCL_R0, RTS, NOP],
         'fsdiv': [MOV_R4_R0, MOV_R5_R1, XOR_R2, DIV0S_R1_R2] + run(32) + [ROTCL_R0, RTS, NOP],
         'fshort': [MOV_R4_R0, MOV_R5_R1, XOR_R2, DIV0U] + run(3) + [ROTCL_R0, RTS, NOP],
         'flone': [MOV_R4_R0, MOV_R5_R1, DIV1_R1_R2, RTS, NOP]}


class TestGenDiv1(unittest.TestCase):
    def test_gen_div1(self):
        bad = []
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        shutil.copytree(TOOLS, os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        code, lines, a = b'', [], BASE
        for n, ws in FUNCS.items():
            code += b''.join(struct.pack('<H', w) for w in ws)
            lines.append('F %08x %d %s' % (a, 2 * len(ws), n))
            a += 2 * len(ws)
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('\n'.join(lines) + '\n')
        os.makedirs(os.path.join(tmp, 'src'))
        script = ("import sys; sys.path.insert(0, 'tools'); sys.path.insert(0, 'tools/5-generated/gen_equiv')\n"
                  "import re, toolpath, gen_core, gen_drv\n"
                  "for n in %r:\n"
                  "    try:\n"
                  "        src, c = gen_drv.build(n, 'r0', False)\n"
                  "        print('OUT', n, len(src.splitlines()), src.count('for ('), len(re.findall(r'^\\s+unsigned\\b', src, re.M)))\n"
                  "    except gen_core.Skip as e:\n"
                  "        print('SKIP', n, e)\n" % (tuple(FUNCS),))
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True).stdout
        got = {}
        for l in out.splitlines():
            p = l.split(None, 2)
            if p and p[0] in ('OUT', 'SKIP'):
                got[p[1]] = (p[0], p[2])
        for n in ('fudiv', 'fsdiv'):
            k, v = got.get(n, ('?', out[-300:]))
            if k != 'OUT':
                bad.append('%s: not written: %s' % (n, v[:160]))
            else:
                lines_, loops, decls = map(int, v.split())
                if decls:
                    bad.append('%s: %d declaration(s) in the middle of a block (SHC takes declarations at the top of a block only)' % (n, decls))
                if loops != 1 or lines_ > 120:
                    bad.append('%s: %d lines, %d loops (expected the steps in one loop, under 120 lines)' % (n, lines_, loops))
        if got.get('fshort', ('?',))[0] != 'OUT':
            bad.append('short: not written: %s' % (got.get('fshort', ('?', out[-300:]))[1][:160]))
        if got.get('flone', ('?',))[0] != 'SKIP' or 'div1 without div0' not in got['flone'][1]:
            bad.append('lone: expected a skip "div1 without div0": %r' % (got.get('flone'),))
        # the quotient-bit rule against the simulator
        sys.path[:0] = [os.path.join(TOOLS, 'sim'), TOOLS]
        import sh4sim
        rnd = random.Random(1)
        cpu = sh4sim.CPU.__new__(sh4sim.CPU) if hasattr(sh4sim, 'CPU') else None
        if cpu is None:
            bad.append('model: sh4sim has no CPU class to compare with')
        else:
            M32 = 0xFFFFFFFF
            for _ in range(20000):
                rv, dv, t, m, q = rnd.getrandbits(32), rnd.getrandbits(32), rnd.getrandbits(1), rnd.getrandbits(1), rnd.getrandbits(1)
                cpu.r = [0] * 16
                cpu.r[1], cpu.r[2] = dv, rv
                cpu.t, cpu.q, cpu.mq = t, q, m
                cpu.div1(2, 1)
                oq, qn = q, rv >> 31
                r2 = ((rv << 1) | t) & M32
                t0 = r2
                if oq == m:
                    r2 = (r2 - dv) & M32
                    t1 = int(r2 > t0)
                else:
                    r2 = (r2 + dv) & M32
                    t1 = int(r2 < t0)
                qn = t1 ^ qn ^ m
                if (cpu.r[2], cpu.q, cpu.t) != (r2, qn, int(qn == m)):
                    bad.append('model: rv=%08x dv=%08x t=%d m=%d q=%d: simulator %r, rule %r' % (rv, dv, t, m, q, (cpu.r[2], cpu.q, cpu.t), (r2, qn, int(qn == m))))
                    break
        if bad:
            self.fail('[ERROR] gen div1 check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
