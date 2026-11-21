#!/usr/bin/env python3
"""Two device-register reads stay two statements, in the original's order (scripts/tools/5-generated/gen_equiv/gen_drv.py inline_single).
A temporary read once is written into its use; with two of them feeding one expression the compiler reads either first, and the generated
C read a PVR register after the one the original read second (Power Stone FUN_0c100260: 810C, then 80DC, came out 80DC, then 810C). A read of
main RAM may still be folded. No game data, no compiler: the helper on small bodies. Stdlib only.

    two_device    t1 = *(int *)0xA05F810C ; t2 = *(int *)0xA05F80DC ; store (t1 & 0x3FF) + (t2 & 0x3FF)      both stay statements
    one_device    t1 = *(int *)0xA05F810C ; store t1 & 0x3FF                                                  a lone device read is not folded either
    ram_reads     t1 = *(int *)0xC800000 ; t2 = *(int *)0xC800004 ; store t1 + t2                              plain RAM reads fold as before
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
TOOLS = os.path.join(SKILL, 'scripts', 'tools')
BASE = 0x8C010000

SCRIPT = r'''
import sys
sys.path[:0] = ['tools', 'tools/5-generated/gen_equiv']
import toolpath, gen_core, gen_drv
def run(name, body):
    decls = ['int t1;', 'int t2;']
    out = gen_drv.inline_single(list(body), decls)
    print('@@@@ ' + name); print('\n'.join(out))
run('two_device', ['t1 = *(int *)0xA05F810C;', 't2 = *(int *)0xA05F80DC;', '*(int *)0xC800000 = ((t1 & 0x3FF) + (t2 & 0x3FF));'])
run('one_device', ['t1 = *(int *)0xA05F810C;', '*(int *)0xC800000 = (t1 & 0x3FF);'])
run('ram_reads', ['t1 = *(int *)0xC800000;', 't2 = *(int *)0xC800004;', '*(int *)0xC800008 = (t1 + t2);'])
'''


class TestDeviceReadOrder(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        open(os.path.join(cls.tmp.name, '1ST_READ.BIN'), 'wb').write(b'\x0b\x00\x09\x00' * 8)
        open(os.path.join(cls.tmp.name, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(cls.tmp.name, 'functions.txt'), 'w').write('F %08x 8 f\n' % BASE)
        for d in ('src', 'tests', 'build'):
            os.makedirs(os.path.join(cls.tmp.name, d))
        shutil.copytree(TOOLS, os.path.join(cls.tmp.name, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        r = subprocess.run([sys.executable, '-B', '-c', SCRIPT], cwd=cls.tmp.name, capture_output=True, text=True)
        cls.out = r.stdout + r.stderr
        cls.parts = {}
        for chunk in cls.out.split('@@@@ ')[1:]:
            name, _, text = chunk.partition('\n')
            cls.parts[name.strip()] = text.strip().splitlines()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_two_device_reads_stay_statements_in_order(self):
        got = self.parts.get('two_device')
        self.assertIsNotNone(got, self.out)
        self.assertEqual(len(got), 3, self.out)
        self.assertIn('0xA05F810C', got[0])
        self.assertIn('0xA05F80DC', got[1])

    def test_a_lone_device_read_is_not_folded(self):
        self.assertEqual(len(self.parts.get('one_device', [])), 2, self.out)

    def test_plain_ram_reads_still_fold(self):
        got = self.parts.get('ram_reads')
        self.assertIsNotNone(got, self.out)
        self.assertEqual(len(got), 1, 'reads of main RAM are folded as before:\n' + self.out)


# --- the generator writes device reads as volatile reads, in the original's order ---

DEV_CODE = [0xD103, 0xD204, 0x6012, 0x6322, 0x303C, 0x000B, 0x0009, 0x0009]      # mov.l @pool1,r1 ; mov.l @pool2,r2 ; mov.l @r1,r0 ; mov.l @r2,r3 ; add r3,r0 ; rts ; nop
DEV_POOL = [0xA05F810C, 0xA05F80DC]                                                   # read first, read second


class TestDeviceReadsAreVolatile(unittest.TestCase):
    """A plain load may be scheduled by the compiler before another one that the original made first: the order of two device reads is the
    original's only when the C says volatile. A read of main RAM stays a plain one."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        data = b''.join(struct.pack('<H', w) for w in DEV_CODE) + b''.join(struct.pack('<I', v) for v in DEV_POOL)
        open(os.path.join(cls.tmp.name, '1ST_READ.BIN'), 'wb').write(data)
        open(os.path.join(cls.tmp.name, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(cls.tmp.name, 'functions.txt'), 'w').write('F %08x %d devpair\n' % (BASE, len(data)))
        for d in ('src', 'tests', 'build'):
            os.makedirs(os.path.join(cls.tmp.name, d))
        shutil.copytree(TOOLS, os.path.join(cls.tmp.name, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        script = ("import sys; sys.path[:0] = ['tools', 'tools/5-generated/gen_equiv']; import toolpath, gen_core, gen_drv\n"
                  "s, c = gen_drv.build('devpair', 'r0', False); print(s)\n")
        r = subprocess.run([sys.executable, '-B', '-c', script], cwd=cls.tmp.name, capture_output=True, text=True)
        cls.out = r.stdout + r.stderr

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_both_device_reads_are_volatile_and_in_order(self):
        i, j = self.out.find('0xA05F810C'), self.out.find('0xA05F80DC')
        self.assertTrue(0 <= i < j, self.out)
        for addr in ('0xA05F810C', '0xA05F80DC'):
            line = [l for l in self.out.splitlines() if addr in l][0]
            self.assertIn('volatile', line, 'a device read is a volatile read:\n' + self.out)


if __name__ == '__main__':
    unittest.main()
