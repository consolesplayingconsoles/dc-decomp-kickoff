#!/usr/bin/env python3
"""A jump table of 32-bit addresses is a switch (scripts/tools/5-generated/gen_equiv/gen_core.py find_switches_abs). No game data, no compiler.
Stdlib only.

`mova table,r0; mov.l @(r0,rX),r0; jmp @r0` over absolute addresses (rX holds four times the index) was read as an indirect call through the
table, and the C called a table entry as a function. Only the table of 16-bit offsets (`mov.w`, `braf`) was a switch.

    check.py      a three-arm table, the arms return 1, 2 and 3:
                    switch    the C is a switch, not a call
                    four      the cases are four apart (0 and 4, the last arm is the default), not two
    carried       a value set in the block before the switch's own block and read only in an arm is written: the register
                  liveness did not follow the table, took it for dead and dropped it, and the arm read a variable never set
"""
import unittest
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
BASE = 0x0C010000
W = lambda ws: b''.join(struct.pack('<H', w) for w in ws)
L = lambda v: struct.pack('<I', v)


def run_in_repo(code, script):
    """The output of a python script run in a small repo (one function `fn` made of these bytes) that has a copy of the tools."""
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d fn\n' % (BASE, len(code)))
        os.makedirs(os.path.join(tmp, 'src'))
        return subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, universal_newlines=True).stdout
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def build(code, ret, form=''):
    """The C the generator writes for the function, or the text 'SKIPPED reason'."""
    return run_in_repo(code, "import os, sys; os.environ['GEN_FORM'] = %r; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                             "try:\n"
                             "    print(gen_drv.build('fn', %r, False)[0])\n"
                             "except gen_core.Skip as e:\n"
                             "    print('SKIPPED ' + str(e))\n" % (form, ret))


# mov r4,r2 / shll2 r2 / mova table,r0 / mov.l @(r0,r2),r0 / jmp @r0 / nop, then three addresses, then three arms returning 1, 2 and 3
TABLE_FN = (W([0x6243, 0x4208, 0xC701, 0x002E, 0x402B, 0x0009]) + L(BASE + 0x18) + L(BASE + 0x1E) + L(BASE + 0x24)
            + W([0xE001, 0x000B, 0x0009, 0xE002, 0x000B, 0x0009, 0xE003, 0x000B, 0x0009]))


SWITCHED = """int fn(int a4)
{
    int R5;
    int R6;

    R5 = 7;
    L_C010000:;
    R6 = a4;
    switch (R6) { case 0: goto L_C010010; case 4: goto L_C010020; }
    return R6;
    L_C010020:;
    return 2;
    L_C010010:;
    return R5;
}"""


# mov #7,r5 / bra D / nop / D: mov r4,r2 / shll2 r2 / mova table,r0 / mov.l @(r0,r2),r0 / jmp @r0 / nop / nop, the table, then
# arms returning r5, 2 and 3
CARRIED_FN = (W([0xE507, 0xA000, 0x0009, 0x6243, 0x4208, 0xC702, 0x002E, 0x402B, 0x0009, 0x0009])
              + L(BASE + 0x20) + L(BASE + 0x26) + L(BASE + 0x2C)
              + W([0x6053, 0x000B, 0x0009, 0xE002, 0x000B, 0x0009, 0xE003, 0x000B, 0x0009]))


class TestAbsTable(unittest.TestCase):
    def test_abstable(self):
        out = build(TABLE_FN, 'r0')
        bad = []
        if 'SKIPPED' in out or 'switch' not in out:
            bad.append('switch: the table jump is not a switch:\n%s' % out)
        if 'case 0' not in out or 'case 4' not in out or 'case 2' in out:
            bad.append('four: the cases are not four apart:\n%s' % out)
        if bad:
            self.fail('[ERROR] abstable check failed:\n' + '\n'.join(bad))

    def test_names_not_shared_across_arms(self):
        out = run_in_repo(b'\x09\x00' * 4, "import sys; sys.path.insert(0, 'tools'); import toolpath, splitflat\n"
                                           "print(splitflat.recolor(%r))\n" % SWITCHED)
        first = re.search(r'(\w+) = 7;', out)
        index = re.search(r'(\w+) = a4;', out)
        self.assertTrue(first and index, out)
        self.assertNotEqual(first.group(1), index.group(1), 'one name for the value an arm returns and the index:\n%s' % out)

    def test_carried_into_an_arm(self):
        out = build(CARRIED_FN, 'r0', 'flat')
        self.assertIn('switch', out)
        self.assertRegex(out, r'\b(0x7|7)\b', 'the 7 an arm returns is never written:\n%s' % out)


if __name__ == '__main__':
    unittest.main()
