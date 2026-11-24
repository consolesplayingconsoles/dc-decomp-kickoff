#!/usr/bin/env python3
"""The argument registers a function reads at its entry when a call's delay slot sets one (scripts/tools/5-generated/gen_equiv/
gen_core.py: reg_liveness, entry_reads). No game data, no compiler. Stdlib only.

A call's delay slot runs before the callee: an argument register the slot writes is the slot's value, not the caller's incoming one.
The liveness put the call's argument reads ahead of the slot's writes, so a function whose first call is `jsr @r3 / mov #7,r4` was
taken to read its own incoming r4, and every caller was compared on a register nothing reads: Power Stone 2 FUN_0c101b30 (int
FUN_0c101b30(void)), whose caller FUN_0c101000 DIFFERS on `call 1/1: original ["0C101B30", ["0C290750"], []] / C [..., ["00000003"], []]`.

    check.py      set      jsr g / mov #7,r4       (g reads r4): r4 is NOT read at the entry
                  load     jsr g / mov.l @r5,r4    : r5 is read, r4 is not
                  passed   jsr g / nop             : the incoming r4 goes on to g, r4 IS read
                  update   jsr g / add #1,r4       : the slot reads r4 to make the value, r4 IS read
"""
import unittest
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
BASE = 0x0C010000
# each: mov.l @(pool),r3 / jsr @r3 / <slot> / rts / nop / pad ; pool at +0xC: g.   g: mov r4,r0 / rts / nop
SLOTS = [('set', 0xE407, []), ('load', 0x6452, ['r5']), ('passed', 0x0009, ['r4']), ('update', 0x7401, ['r4'])]
G = [0x6043, 0x000B, 0x0009]


class TestGenSlotArgs(unittest.TestCase):
    def test_slotargs(self):
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
            code = bytearray(0x50)
            funcs = []
            for k, (name, slot, _) in enumerate(SLOTS):
                at = 0x10 * k
                code[at:at + 12] = b''.join(struct.pack('<H', w) for w in (0xD302, 0x430B, slot, 0x000B, 0x0009, 0x0009))
                code[at + 12:at + 16] = struct.pack('<I', BASE + 0x40)
                funcs.append('F %08x 16 %s' % (BASE + at, name))
            code[0x40:0x46] = b''.join(struct.pack('<H', w) for w in G)
            funcs.append('F %08x 6 g' % (BASE + 0x40))
            with open(os.path.join(tmp, '1ST_READ.BIN'), 'wb') as f:
                f.write(bytes(code))
            with open(os.path.join(tmp, 'BASE'), 'w') as f:
                f.write('%08X\n' % BASE)
            with open(os.path.join(tmp, 'functions.txt'), 'w') as f:
                f.write('\n'.join(funcs) + '\n')
            os.makedirs(os.path.join(tmp, 'src'))
            script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core\n"
                      "for n in %r:\n"
                      "    for fn in (gen_core.entry_reads, gen_core.entry_reads_sure):\n"
                      "        r = fn(n)\n"
                      "        print(n, fn.__name__, 'None' if r is None else ','.join(sorted(r)))\n" % [s[0] for s in SLOTS])
            out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 universal_newlines=True).stdout
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        want = ''.join('%s %s %s\n' % (n, fn, ','.join(r)) for n, _, r in SLOTS for fn in ('entry_reads', 'entry_reads_sure'))
        self.assertEqual(out, want, '[ERROR] gen_slotargs check failed:\n' + out)


if __name__ == '__main__':
    unittest.main()
