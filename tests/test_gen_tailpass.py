#!/usr/bin/env python3
"""A tail call to a callee that reads more argument registers than the caller sets, in the flat form (scripts/tools/5-generated/
gen_equiv/gen_core.py: reg_liveness, exec_flat). No game data, no compiler. Stdlib only.

The flat form writes every register the function names as a C variable (R5) and copies an incoming argument into it (`R5 = a5;`) only
when the register is live at the entry. A tail call (`jmp @rN` to another function) read nothing in that liveness, so a caller that
names r5 on another path and tail-calls a callee reading r5 on this one passed the variable R5, never set: Power Stone 2 FUN_0c0ed33c
-> FUN_0c03f346 (four integers, forwarded to a handler), `FUN_0c03f346(v0_0, R5, a6, a7)`, DIFFERS on the call's second argument,
while r6 and r7, named nowhere in the function, went as a6 and a7. The tail call reads the callee's argument registers, as a jsr does.

    check.py      untouched  r5 named on the other path only, tail call to a callee reading r4 and r5: the call gets the incoming a5
                  far        the same with the callee's address loaded nine instructions before the jmp (the epilogue between)
                  between    another call runs before the tail call: r5 is that callee's to change (r4-r7 are scratch on the SH-4), the
                             incoming a5 is NOT passed on
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

# fa: rts / nop (touches nothing).  fw: mov.l r4,@r5 / rts / nop (reads r4 and r5)
FA = [0x000B, 0x0009]
FW = [0x2542, 0x000B, 0x0009]
# untouched: tst r4,r4 / bt L / mov.l @(pool),r1 / jmp @r1 / nop / L: mov #7,r5 / mov.l r5,@r4 / rts / nop / pad ; pool at 0x14: fw
UNTOUCHED = [0x2448, 0x8902, 0xD103, 0x412B, 0x0009, 0xE507, 0x2452, 0x000B, 0x0009, 0x0009]
# far: as untouched, the target loaded nine instructions before the jmp (an epilogue's pops lie between: FUN_0c151cae) ; pool at 0x24
FAR = [0x2448, 0x890B, 0xD107] + [0x0009] * 9 + [0x412B, 0x0009, 0xE507, 0x2452, 0x000B, 0x0009]
# between: tst r4,r4 / bt L / sts.l pr,@-r15 / mov.l @(pool),r1 / jsr @r1 / nop / lds.l @r15+,pr / mov.l @(pool),r1 / jmp @r1 / nop /
#          L: mov #7,r5 / mov.l r5,@r4 / rts / nop ; pools at 0x1C: fa, 0x20: fw
BETWEEN = [0x2448, 0x8907, 0x4F22, 0xD105, 0x410B, 0x0009, 0x4F26, 0xD104, 0x412B, 0x0009, 0xE507, 0x2452, 0x000B, 0x0009]


def build(caller, pools, tmp, form):
    code = bytearray(0x40)
    code[0:2 * len(caller)] = W(caller)
    for off, target in pools:
        code[off:off + 4] = struct.pack('<I', target)
    code[0x30:0x34] = W(FA)
    code[0x34:0x3A] = W(FW)
    with open(os.path.join(tmp, '1ST_READ.BIN'), 'wb') as f:
        f.write(bytes(code))
    with open(os.path.join(tmp, 'BASE'), 'w') as f:
        f.write('%08X\n' % BASE)
    with open(os.path.join(tmp, 'functions.txt'), 'w') as f:
        f.write('F %08x 40 xform\nF %08x 4 fa\nF %08x 6 fw\n' % (BASE, BASE + 0x30, BASE + 0x34))
    os.makedirs(os.path.join(tmp, 'src'), exist_ok=True)
    shutil.rmtree(os.path.join(tmp, 'state'), ignore_errors=True)
    script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
              "try:\n"
              "    print(gen_drv.build('xform', 'r0', False)[0])\n"
              "except gen_core.Skip as e:\n"
              "    print('SKIPPED ' + str(e))\n")
    env = dict(os.environ, GEN_FORM=form)
    env.pop('GEN_FRAME', None)
    return subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True, env=env).stdout


def second_arg(out):
    """What the C passes as fw's second argument, through one copy (`R5 = a5;` then `fw(x, R5)`): '' when there is none."""
    import re
    m = re.search(r'\bfw\)*\(([^;]*)\);', out)
    args = [a.strip() for a in m.group(1).split(',')] if m else []
    if len(args) < 2:
        return ''
    a = args[1].strip('()')
    c = re.search(r'(?m)^\s*%s = \(*(\w+)\)*;$' % re.escape(a), out)
    return c.group(1) if c and a != 'a5' else a


class TestGenTailPass(unittest.TestCase):
    def test_tailpass(self):
        bad = []
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
            for form in ('flat', 'structured'):
                out = build(UNTOUCHED, [(0x14, BASE + 0x34)], tmp, form)
                if 'SKIPPED' in out or second_arg(out) != 'a5':
                    bad.append('untouched (%s): the tail call does not pass the incoming a5 on:\n%s' % (form, out))
                out = build(FAR, [(0x24, BASE + 0x34)], tmp, form)
                if 'SKIPPED' in out or second_arg(out) != 'a5':
                    bad.append('far (%s): the tail call does not pass the incoming a5 on:\n%s' % (form, out))
                out = build(BETWEEN, [(0x1C, BASE + 0x30), (0x20, BASE + 0x34)], tmp, form)
                if 'SKIPPED' in out or 'fw' not in out or second_arg(out) == 'a5':
                    bad.append('between (%s): after another call r5 is not the incoming argument, a5 must not be passed:\n%s' % (form, out))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if bad:
            self.fail('[ERROR] gen_tailpass check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
