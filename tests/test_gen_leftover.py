#!/usr/bin/env python3
"""What the generator passes to a callee that reads an argument register the caller set earlier (scripts/tools/5-generated/gen_equiv/
gen_core.py). No game data, no compiler. Stdlib only.

A callee that reads r4 gets the value the caller put there when nothing in between can have changed it. After ANOTHER call the register
is the callee's to change (r4-r7 are scratch in the SH-4 calling convention: SHC never keeps a value there across a call), so the
generator leaves the argument out: passing the value the register held BEFORE the call would assume that call left r4 alone, which the
code does not say and the checker's mocked calls (which leave every register as it was) cannot show. Power Stone 2 FUN_0c05b4e4 was
suspected of this; its regenerated C is EQUIVALENT on all 61 full-coverage cases, so no rule was added; this file keeps the boundary.

    check.py      direct   `mov #5,r4` then the call that reads r4: the call gets 0x5
                  between  `mov #5,r4`, an unrelated call, then the call that reads r4: the call gets NO argument (the register is
                           unknown after the first call; carrying 0x5 across it would be an assumption about that callee)
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
W = lambda ws: b''.join(struct.pack('<H', w) for w in ws)

# fa: rts / nop (touches nothing).  fb: mov.l r4,@r5 / rts / nop (reads r4 and r5)
FA = [0x000B, 0x0009]
FB = [0x2542, 0x000B, 0x0009]
# xform, direct: mov #5,r4 / mov.l @(pool),r2 / jsr @r2 / nop / rts / nop ; pool: fb
DIRECT = [0xE405, 0xD202, 0x420B, 0x0009, 0x000B, 0x0009]
# xform, between: mov #5,r4 / jsr fa / nop / jsr fb / nop / rts / nop ; pools: fa, fb
BETWEEN = [0xE405, 0xD104, 0x410B, 0x0009, 0xD203, 0x420B, 0x0009, 0x000B, 0x0009]


def build(caller, pools, tmp):
    code = bytearray(0x30)
    code[0:2 * len(caller)] = W(caller)
    for off, target in pools:
        code[off:off + 4] = struct.pack('<I', target)
    code[0x20:0x24] = W(FA)
    code[0x24:0x2A] = W(FB)
    open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(bytes(code))
    open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
    open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x 24 xform\nF %08x 4 fa\nF %08x 6 fb\n' % (BASE, BASE + 0x20, BASE + 0x24))
    os.makedirs(os.path.join(tmp, 'src'), exist_ok=True)
    script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
              "try:\n"
              "    print(gen_drv.build('xform', 'r0', False)[0])\n"
              "except gen_core.Skip as e:\n"
              "    print('SKIPPED ' + str(e))\n")
    return subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True).stdout


class TestGenLeftover(unittest.TestCase):
    def test_leftover(self):
        bad = []
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
            out = build(DIRECT, [(0x0C, BASE + 0x24)], tmp)
            if 'SKIPPED' in out or 'fb(0x5' not in out:
                bad.append('direct: the call that reads r4 right after `mov #5,r4` does not get 0x5:\n%s' % out)
            out = build(BETWEEN, [(0x14, BASE + 0x20), (0x18, BASE + 0x24)], tmp)
            if 'SKIPPED' in out or 'fb()' not in out or '0x5' in out:
                bad.append('between: after another call the register is unknown, the call must carry no argument:\n%s' % out)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if bad:
            self.fail('[ERROR] gen_leftover check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
