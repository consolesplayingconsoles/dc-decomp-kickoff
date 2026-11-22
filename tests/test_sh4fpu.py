"""The FPU instructions the hardware computes with its own approximating datapath give the hardware's bits in the simulator.

fipr, ftrv, fsrra and fsca run on one multiplier block in the SH-4 (truncated Booth products, a cubic from a ROM for
fsrra / fsca); the simulator used exact double arithmetic and missed the hardware by an ulp or two, and it got the special
operands wrong: with FPSCR.DN = 1 a denormal operand is a zero (0 * inf is NaN, not inf), and fsrra of a NaN is a NaN.
The model is scripts/tools/sim/sh4fpu.py, a port of a bit-exact model verified against a Dreamcast.

The expected words below were measured on a Dreamcast (hwverify, dcload-serial): the sequence that normalises a vector --
three floats into fr4-fr6, fldi0 fr7, fipr fv4,fv4, fsrra fr7, fmul fr7 into each -- with the inputs listed.

No game data and no compiler. Run: python3 -m unittest tests.test_sh4fpu
"""
import os
import struct
import sys
import unittest

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL, 'scripts', 'tools'))
import toolpath  # noqa: E402,F401
import sh4sim  # noqa: E402
import sh4fpu  # noqa: E402

CODE = 0x8C010000
NORMALISE = (0xF78D,                      # fldi0 fr7
             0xF5ED,                      # fipr fv4,fv4   -> fr7 = x*x + y*y + z*z
             0xF77D,                      # fsrra fr7
             0xF472, 0xF572, 0xF672)      # fmul fr7,fr4 / fr5 / fr6


def run(ops, fr):
    memory = sh4sim.Memory()
    memory.load(CODE, b''.join(struct.pack('<H', op) for op in ops))
    cpu = sh4sim.CPU(memory)
    cpu.pc = CODE
    for n, v in fr.items():
        cpu.fr[n] = v
    for _ in ops:
        cpu.step()
    return cpu


def normalise(x, y, z):
    cpu = run(NORMALISE, {4: x, 5: y, 6: z})
    return cpu.fr[4], cpu.fr[5], cpu.fr[6]


class MeasuredOnTheConsole(unittest.TestCase):
    def test_a_unit_vector_comes_out_an_ulp_short_of_one(self):
        self.assertEqual(normalise(0xC0400000, 0x0000000B, 0x00000003), (0xBF7FFFFF, 0, 0))            # -3, two denormals
        self.assertEqual(normalise(0x42C80000, 0x00000004, 0x00000008), (0x3F7FFFFE, 0, 0))            # 100
        self.assertEqual(normalise(0x4E6E6B28, 0x00000100, 0x00000001), (0x3F7FFFFF, 0, 0))

    def test_mixed_vectors(self):
        self.assertEqual(normalise(0x3F800000, 0x00000000, 0xC0400000), (0x3EA1E89A, 0, 0xBF72DCE7))   # 1, 0, -3
        self.assertEqual(normalise(0x40000000, 0x3F800000, 0x40200000), (0x3F18A61E, 0x3E98A61E, 0x3F3ECFA5))
        self.assertEqual(normalise(0x40200000, 0x40200000, 0x00000003), (0x3F3504F2, 0x3F3504F2, 0))
        self.assertEqual(normalise(0x00000005, 0x40000000, 0x42C80000), (0, 0x3CA3CEA6, 0x3F7FF2E3))

    def test_a_vector_of_denormals_is_a_zero_vector_and_gives_nan(self):
        # the length is 0, fsrra gives +inf, and each denormal component is a zero: 0 * inf
        self.assertEqual(normalise(0x00000000, 0x0000000D, 0x00000008), (0x7FBFFFFF,) * 3)
        self.assertEqual(normalise(0x0000000C, 0x00000018, 0x00000004), (0x7FBFFFFF,) * 3)

    def test_a_nan_component_gives_nan_everywhere(self):
        self.assertEqual(normalise(0x00000002, 0x00000010, 0x7FFFFFFF), (0x7FBFFFFF,) * 3)
        self.assertEqual(normalise(0x00000018, 0xFFFFFFFE, 0xC0400000), (0x7FBFFFFF,) * 3)
        self.assertEqual(normalise(0x3F800000, 0xFFFFFFFF, 0xC0400000), (0x7FBFFFFF,) * 3)


class Model(unittest.TestCase):
    def test_fsrra_special_operands(self):
        self.assertEqual(sh4fpu.fsrra(0x7F800000), 0)                      # +inf -> +0
        self.assertEqual(sh4fpu.fsrra(0xFF800000), 0x7FBFFFFF)             # -inf -> qNaN
        self.assertEqual(sh4fpu.fsrra(0x80000000), 0xFF800000)             # -0 -> -inf
        self.assertEqual(sh4fpu.fsrra(0x00000003), 0x7F800000)             # a denormal is +0 -> +inf
        self.assertEqual(sh4fpu.fsrra(0xBF800000), 0x7FBFFFFF)             # negative -> qNaN
        self.assertEqual(sh4fpu.fsrra(0x3F800000), 0x3F800000)             # 1 -> 1

    def test_fsca_quarter_turns(self):
        self.assertEqual(sh4fpu.fsca(0x0000), (0, 0x3F800000))
        self.assertEqual(sh4fpu.fsca(0x4000), (0x3F800000, 0))
        self.assertEqual(sh4fpu.fsca(0x14000), sh4fpu.fsca(0x4000))       # FPUL[31:16] is ignored

    def test_fipr_special_operands(self):
        one, inf, ninf = 0x3F800000, 0x7F800000, 0xFF800000
        self.assertEqual(sh4fpu.fipr([inf, 0, 0, 0], [0, 0, 0, 0]), 0x7FBFFFFF)                  # inf * 0
        self.assertEqual(sh4fpu.fipr([inf, inf, 0, 0], [one, 0xBF800000, 0, 0]), 0x7FBFFFFF)     # +inf and -inf
        self.assertEqual(sh4fpu.fipr([inf, 0, 0, 0], [one, 0, 0, 0]), inf)
        self.assertEqual(sh4fpu.fipr([ninf, 0, 0, 0], [one, 0, 0, 0]), ninf)
        self.assertEqual(sh4fpu.fipr([0x80000000] * 4, [one] * 4), 0)                           # an exact zero sum is +0


class DenormalOperands(unittest.TestCase):
    def test_a_denormal_times_infinity_is_nan(self):
        cpu = run((0xF012,), {0: 0x00000005, 1: 0x7F800000})              # fmul fr1,fr0
        self.assertEqual(cpu.fr[0], 0x7FBFFFFF)

    def test_a_denormal_plus_one_is_one(self):
        cpu = run((0xF010,), {0: 0x00000005, 1: 0x3F800000})              # fadd fr1,fr0
        self.assertEqual(cpu.fr[0], 0x3F800000)


if __name__ == '__main__':
    unittest.main()
