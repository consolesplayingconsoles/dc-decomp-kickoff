#!/usr/bin/env python3
"""A function listed shorter than its code (tools/1-2-baseline/checksizes.py names them: a literal pool in the middle of its body, the
sweep stopped at it) must not get generated C: the generator read the body up to the listed size, ran off its end, and wrote
`return r0` there, so the C stopped before the original did (Power Stone vmsfs_mount2: the call after the pool left out, the
base address in r0 returned as the result). Skipped, with the reason. No game data, no compiler: a synthetic executable of small
functions. Stdlib only.

    whole      mov #1,r0 ; rts ; nop                                  listed in full: written
    cut_fall   mov #1,r0 ; add #1,r0                                  listed size ends mid-body, no return: skipped
    cut_branch tst r0,r0 ; bf L ; nop ; mov #2,r0 ; L: mov #3,r0 ; rts ; nop     listed up to the `mov #3,r0`: skipped
    cut_bra    tst r0,r0 ; bt L ; nop ; bra OUT ; nop ; L: mov #3,r0     bra to an address past the listed size: skipped
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
NOP, RTS = 0x0009, 0x000B
SLOT = 0x40                                   # every function gets 0x40 bytes of the image; its listed size is what the test says
ORDER = ['whole', 'cut_fall', 'cut_branch', 'cut_bra']
ADDR = {n: BASE + i * SLOT for i, n in enumerate(ORDER)}


def bra(at, to):
    return 0xA000 | (((to - (at + 4)) >> 1) & 0xFFF)


def bf(at, to):
    return 0x8B00 | (((to - (at + 4)) >> 1) & 0xFF)


def bt(at, to):
    return 0x8900 | (((to - (at + 4)) >> 1) & 0xFF)


def image():
    a = ADDR
    code = {
        'whole': ([0xE001, RTS, NOP], 6),
        'cut_fall': ([0xE001, 0x7001, RTS, NOP], 4),
        # tst r0,r0 ; bf L ; nop ; mov #2,r0 ; L: mov #3,r0 ; rts ; nop     (the listed size stops after `mov #3,r0`)
        'cut_branch': ([0x2448, bf(a['cut_branch'] + 2, a['cut_branch'] + 10), NOP, 0xE002, 0xE003, RTS, NOP], 10),
        # tst r0,r0 ; bt L ; nop ; bra OUT ; nop ; L: mov #3,r0 ; rts ; nop ; OUT: rts ; nop        (listed size stops after `mov #3,r0`)
        'cut_bra': ([0x2448, bt(a['cut_bra'] + 2, a['cut_bra'] + 10), NOP, bra(a['cut_bra'] + 6, a['cut_bra'] + 0x20), NOP,
                     0xE003, RTS, NOP], 12),
    }
    out, sizes = b'', {}
    for n in ORDER:
        words, listed = code[n]
        body = b''.join(struct.pack('<H', w) for w in words)
        sizes[n] = listed
        out += body + struct.pack('<H', NOP) * ((SLOT - len(body)) // 2)
    # the target of cut_bra's `bra`: a return, 0x20 bytes into its slot
    off = ORDER.index('cut_bra') * SLOT + 0x20
    out = out[:off] + struct.pack('<HH', RTS, NOP) + out[off + 4:]
    return out, sizes


class TestTruncatedFunction(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        data, sizes = image()
        open(os.path.join(cls.tmp.name, '1ST_READ.BIN'), 'wb').write(data)
        open(os.path.join(cls.tmp.name, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(cls.tmp.name, 'functions.txt'), 'w').write(
            ''.join('F %08x %d %s\n' % (ADDR[n], sizes[n], n) for n in ORDER))
        for d in ('src', 'tests', 'build'):
            os.makedirs(os.path.join(cls.tmp.name, d))
        shutil.copytree(TOOLS, os.path.join(cls.tmp.name, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        script = ("import sys; sys.path[:0] = ['tools', 'tools/5-generated/gen_equiv']; import toolpath, gen_core, gen_drv\n"
                  "for n in sys.argv[1:]:\n"
                  "    try:\n"
                  "        s, c = gen_drv.build(n, 'r0', False); print(n, 'WRITTEN'); print(s)\n"
                  "    except Exception as e: print(n, 'SKIPPED', type(e).__name__, e)\n")
        r = subprocess.run([sys.executable, '-B', '-c', script] + ORDER, cwd=cls.tmp.name, capture_output=True, text=True)
        cls.out = r.stdout + r.stderr

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def verdict(self, name):
        for line in self.out.splitlines():
            if line.startswith(name + ' '):
                return line
        self.fail('no verdict for %s in:\n%s' % (name, self.out))

    def test_function_listed_in_full_is_written(self):
        self.assertIn('WRITTEN', self.verdict('whole'))

    def test_body_that_runs_off_its_listed_end_is_skipped(self):
        self.assertIn('SKIPPED', self.verdict('cut_fall'), self.out)
        self.assertIn('listed size', self.verdict('cut_fall'))

    def test_body_cut_after_a_branch_target_is_skipped(self):
        self.assertIn('SKIPPED', self.verdict('cut_branch'), self.out)

    def test_branch_past_the_listed_size_is_skipped(self):
        self.assertIn('SKIPPED', self.verdict('cut_bra'), self.out)
        self.assertIn('listed size', self.verdict('cut_bra'))


if __name__ == '__main__':
    unittest.main()
