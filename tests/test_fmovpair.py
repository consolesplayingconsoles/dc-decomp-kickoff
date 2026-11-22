"""An FMOV register pair moves in the order of the two singles: the first register at the lower address.

On the hardware (and in Flycast) `fmov @Rm,DRn` puts the word at Rm in FR(2n) and the word at Rm+4 in FR(2n+1), and `fmov DRm,@Rn` stores
them back the same way; a natural float[4][4] loaded into XMTRX with pairs relies on it. The simulator (scripts/tools/sim/sh4sim.py) and the
generator (scripts/tools/5-generated/gen_equiv/gen_core.py) moved them swapped.

No game data and no compiler. Run: python3 -m unittest tests.test_fmovpair   (or: python3 tests/test_fmovpair.py)
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(SKILL, 'scripts', 'tools')
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401
import sh4sim  # noqa: E402

FIRST, SECOND = 0x3F800000, 0x40000000          # 1.0f and 2.0f: the word at the lower address and the one 4 above
CODE, DATA, OUT = 0x8C010000, 0x8C020000, 0x8C030000


def words(*ops):
    return b''.join(struct.pack('<H', op) for op in ops)


def cpu_running(*ops):
    """A CPU with FPSCR.SZ = 1 (pair moves) at the first of ops, r4 pointing at two words and r5 at room for two."""
    memory = sh4sim.Memory()
    memory.load(CODE, words(*ops))
    memory.load(DATA, struct.pack('<II', FIRST, SECOND))
    cpu = sh4sim.CPU(memory)
    cpu.pc, cpu.sz = CODE, 1
    cpu.r[4], cpu.r[5] = DATA, OUT
    return cpu, memory


class SimulatorPairMoves(unittest.TestCase):
    def test_load_into_a_double_register(self):
        cpu, _ = cpu_running(0xF048)                           # fmov @r4,dr0
        cpu.step()
        self.assertEqual((cpu.fr[0], cpu.fr[1]), (FIRST, SECOND))

    def test_load_into_the_other_bank(self):
        cpu, _ = cpu_running(0xF148)                           # fmov @r4,xd0
        cpu.step()
        self.assertEqual((cpu.xf[0], cpu.xf[1]), (FIRST, SECOND))

    def test_store_from_a_double_register(self):
        cpu, memory = cpu_running(0xF50A)                      # fmov dr0,@r5
        cpu.fr[0], cpu.fr[1] = FIRST, SECOND
        cpu.step()
        self.assertEqual((memory.read(OUT, 4), memory.read(OUT + 4, 4)), (FIRST, SECOND))

    def test_load_with_post_increment(self):
        cpu, _ = cpu_running(0xF049)                           # fmov @r4+,dr0
        cpu.step()
        self.assertEqual((cpu.fr[0], cpu.fr[1], cpu.r[4]), (FIRST, SECOND, DATA + 8))

    def test_store_with_pre_decrement(self):
        cpu, memory = cpu_running(0xF50B)                      # fmov dr0,@-r5
        cpu.r[5] = OUT + 8
        cpu.fr[0], cpu.fr[1] = FIRST, SECOND
        cpu.step()
        self.assertEqual((memory.read(OUT, 4), memory.read(OUT + 4, 4), cpu.r[5]), (FIRST, SECOND, OUT))


# fschg / fmov @r4,dr0 / fschg / fmov.s fr0,@r5 / mov #4,r0 / fmov.s fr1,@(r0,r5) / rts / nop
COPY_PAIR = (0xF3FD, 0xF048, 0xF3FD, 0xF50A, 0xE004, 0xF517, 0x000B, 0x0009)


class GeneratorPairMoves(unittest.TestCase):
    def test_pair_is_read_in_memory_order(self):
        """fr0 is stored at r5 and fr1 at r5 + r0 (r0 = 4): fr0 must be the word at r4 and fr1 the word at r4 + 4."""
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(TOOLS, os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
            code = words(*COPY_PAIR)
            with open(os.path.join(tmp, '1ST_READ.BIN'), 'wb') as f:
                f.write(code)
            with open(os.path.join(tmp, 'BASE'), 'w') as f:
                f.write('%08X\n' % 0x0C010000)
            with open(os.path.join(tmp, 'functions.txt'), 'w') as f:
                f.write('F %08x %d copy_pair\n' % (0x0C010000, len(code)))
            os.makedirs(os.path.join(tmp, 'src'))
            script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                      "try:\n"
                      "    print(gen_drv.build('copy_pair', 'r0', False)[0])\n"
                      "except gen_core.Skip as e:\n"
                      "    print('SKIPPED ' + str(e))\n")
            out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, universal_newlines=True).stdout
        self.assertNotIn('SKIPPED', out, out)
        lines = out.split('\n')
        direct = [l for l in lines if '(a5 + 0x0)' in l and '=' in l and 'struct' not in l]
        second = [l for l in lines if '+ 4)' in l and 'a4' in l]
        self.assertTrue(direct and second, out)
        self.assertNotIn('+ 4', direct[0], out)            # the first store reads the word at r4 itself
        self.assertIn('a4 + 0x0', direct[0], out)


if __name__ == '__main__':
    unittest.main()
