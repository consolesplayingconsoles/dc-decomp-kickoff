#!/usr/bin/env python3
"""An outlier function cut into parts along its control flow (scripts/tools/6-agentic/parts.py). No game data, no compiler, no
simulator. Stdlib only.

A function far larger than the rest is read in parts, never in one long run (SKILL.md step 6): map cuts it where a block dominates a
region (entered only through its first instruction), with long jumps to one shared exit as the sections' ends; read lists every part
as an entry of a scratch functions.txt, so the generator reads each one as a small function.

    check.py      map       a head that branches to two sections, each ending in a `jmp` through a pool word to one shared exit:
                            two parts at the sections' starts, the exit found as the shared one, the head as glue
                  small     a function under the size limit is one part
                  cross     a branch from one chunk into the middle of another makes its target a cut of its own
                  scratch   the scratch functions.txt splits the function at the cuts (its own name up to the first, part_<address>
                            after), and leaves the other entries as they are
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')
sys.path[:0] = [os.path.join(TOOLS, '6-agentic'), os.path.join(TOOLS, '5-generated', 'gen_equiv'), TOOLS]
import parts  # noqa: E402

B = 0x0C010000
CODE = [(B + 0x00, 'tst', 'r4,r4', None), (B + 0x02, 'bt', '0x%08x' % (B + 0x12), None),
        (B + 0x04, 'mov', '#1,r0', None), (B + 0x06, 'mov', '#2,r1', None), (B + 0x08, 'add', 'r1,r0', None),
        (B + 0x0A, 'add', 'r1,r0', None), (B + 0x0C, 'mov.l', '@(0x%08x,pc),r1' % (B + 0x24), B + 0x20),
        (B + 0x0E, 'jmp', '@r1', None), (B + 0x10, 'nop', '', None),
        (B + 0x12, 'mov', '#3,r0', None), (B + 0x14, 'mov', '#4,r1', None), (B + 0x16, 'add', 'r1,r0', None),
        (B + 0x18, 'add', 'r1,r0', None), (B + 0x1A, 'mov.l', '@(0x%08x,pc),r1' % (B + 0x28), B + 0x20),
        (B + 0x1C, 'jmp', '@r1', None), (B + 0x1E, 'nop', '', None),
        (B + 0x20, 'rts', '', None), (B + 0x22, 'nop', '', None)]


class TestParts(unittest.TestCase):
    def test_parts(self):
        bad = []
        got = parts.parts(CODE, maxn=8, limit=2)
        ps = sorted(a for k, a, n in got if k == 'part')
        ex = [a for k, a, n in got if k == 'exit']
        if ps != [B + 0x04, B + 0x12]:
            bad.append('map: parts at %s, expected the two sections 0c010004 and 0c010012' % ['%08x' % a for a in ps])
        if ex != [B + 0x20]:
            bad.append('map: the shared exit is %s, expected 0c010020' % ['%08x' % a for a in ex])
        if not any(k == 'glue' for k, a, n in got):
            bad.append('map: no glue listed for the head')
        whole = parts.parts(CODE, maxn=100)
        if [k for k, a, n in whole if k == 'part'] != ['part']:
            bad.append('small: a function under the limit is not one part: %r' % whole)
        loop = [(B + 0x00, 'mov', '#0,r0', None), (B + 0x02, 'add', '#1,r0', None), (B + 0x04, 'cmp/eq', '#5,r0', None),
                (B + 0x06, 'bf', '0x%08x' % (B + 0x02), None), (B + 0x08, 'rts', '', None), (B + 0x0A, 'nop', '', None)]
        if parts.cut_points(loop, [B + 0x04]) != [B + 0x02, B + 0x04]:
            bad.append('cross: cuts %s, expected the loop head 0c010002 added' % ['%08x' % a for a in parts.cut_points(loop, [B + 0x04])])
        lines = ['F 0c00fff0 16 before', 'F 0c010000 36 big', 'F 0c010024 8 after']
        want = ['F 0c00fff0 16 before', 'F 0c010000 4 big', 'F 0c010004 14 part_0c010004', 'F 0c010012 14 part_0c010012',
                'F 0c010020 4 part_0c010020', 'F 0c010024 8 after']
        got_lines = parts.scratch_functions(lines, 'big', [B + 0x04, B + 0x12, B + 0x20])
        if got_lines != want:
            bad.append('scratch: %r, expected %r' % (got_lines, want))
        if bad:
            self.fail('[ERROR] parts check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
