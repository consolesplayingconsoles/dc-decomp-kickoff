#!/usr/bin/env python3
"""A case can raise the step limit the original is run under (scripts/tools/5-generated/gen_equiv/gen_drv.py original_runs). No game
data, no compiler. Stdlib only.

The original ran under max(100000, size * 60) steps whatever the case said, so a small function with a long loop could never finish
under the tool: Zombie Revenge nlObjPutInit (134 bytes, a 32 x 96 table fill) takes 347,422 steps with any input, and every case,
drawn or supplied by hand, was thrown out as "does not finish". A hand case's own "steps" (sh4sim.py takes it) is now the limit when
it is larger.

    check.py      `L: dt r4 / bf L / rts / nop` with r4 = 60,000 (120,000 steps, over the 100,000 default):
                    default   no "steps" in the case: the original hits the limit (the case is mended to a short one, or dropped)
                    raised    "steps": 1000000 in the case: it finishes, in about 120,000 steps
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
tmp = tempfile.mkdtemp()
os.chdir(tmp)
open('functions.txt', 'w').write('F 8c020000 8 fn\n')
open('BASE', 'w').write('8C020000\n')
open('1ST_READ.BIN', 'wb').write(bytes([0x10, 0x44, 0xFD, 0x8B, 0x0B, 0x00, 0x09, 0x00]))      # dt r4 / bf L / rts / nop
sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401
import gen_drv  # noqa: E402


def main():
    bad = []
    base = {'about': 'long loop', 'regs': {'r4': '%08X' % 60000}}
    # raised first: a case that hits the default limit is mended, and the repair is remembered for the next run of the function
    n1 = gen_drv.original_runs('fn', dict(base, steps=1000000))[0]
    if n1 is None or not 110000 <= n1 <= 130000:
        bad.append('raised: with "steps": 1000000 the original took %s steps, expected about 120,000' % n1)
    n0 = gen_drv.original_runs('fn', dict(base))[0]
    if n0 is not None and n0 >= 110000:
        bad.append('default: the original finished the long loop in %s steps under the default limit' % n0)      # (a case that hits it is mended: its inputs shrink)
    if bad:
        sys.exit('[ERROR] handsteps check failed:\n' + '\n'.join(bad))
    print('[handsteps] ok: a case\'s own step limit is used when it is larger than the default')


if __name__ == '__main__':
    main()
