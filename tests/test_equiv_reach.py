"""Two things the checker (scripts/tools/equiv.py, with scripts/tools/sh4sim.py) used to pass and the game did not. No game data, no
compiler: hand-assembled SH-4. Stdlib only.

What a call reads through a pointer into the caller's frame (sh4sim frame_reach, equiv same_bufs). The checker compared the words
stored right from the argument on, without a gap, since the last call. Crazy Taxi's SaveBackupData fills its save record's fields
0x44 on, after the record's memmove; the C kept them in locals and passed the record unfilled, and both runs had nothing stored
right at the argument: it passed, and the game never made its save file. Now the callee itself runs on a copy of the memory, and
the frame words it reads before writing them are compared.

    reach      the callee's read of the record's field (36 bytes on) is recorded with the caller's word, and whether it stored it
    differs    one side stores the field and the other does not: the call differs, though nothing was stored at the argument
    agrees     both sides store the same value: no difference
    leftover   neither side stored the field (each frame holds something else there): not compared
    written    a word the callee writes before it reads it is its own output, not something the caller passes: not recorded

An output over an input (equiv alias_variants). Crazy Taxi's SetObjFly calls nlOuterProduct(v, s, s), the cross product over its
second operand. The C wrote out[2] before it had read b[1] and b[2]; every case had its own output, so it passed, and the street
objects never came to rest. Now each case runs again with an output pointer set to an input.

    variant    the pointer the original wrote through is set to each one it read through
    skip       a pointer only read, a value that is no address, an output already equal to the input: no variant
    once       a variant makes no variants of its own
"""
import os
import struct
import sys
import tempfile
import unittest

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(SKILL, 'scripts', 'tools')
BASE = 0x0C010000
CALLEE = 0x0C0F0000
FIELD = 36                      # where in the record the callee reads

MOV_7_R1, MOV_9_R1, NOP = 0xE107, 0xE109, 0x0009
STORE_FIELD = 0x0F16            # mov.l r1,@(r0,r15)


def caller(value_op, store_op):
    """sts.l pr,@-r15 / add #-64,r15 / <value> / mov #36,r0 / <store> / mov r15,r4 / mov.l @(pool),r2 / jsr @r2 / nop /
    add #64,r15 / lds.l @r15+,pr / rts / nop / nop / pool: the callee. r4 points at the record at the frame's start"""
    words = [0x4F22, 0x7FC0, value_op, 0xE000 | FIELD, store_op, 0x64F3, 0xD203, 0x420B, NOP, 0x7F40, 0x4F26, 0x000B, NOP, NOP]
    return struct.pack('<14H', *words) + struct.pack('<I', CALLEE)


READS = struct.pack('<3H', 0x5049, 0x000B, NOP)                     # mov.l @(36,r4),r0 / rts / nop
WRITES_FIRST = struct.pack('<5H', 0xE105, 0x1419, 0x5049, 0x000B, NOP)   # mov #5,r1 / mov.l r1,@(36,r4) / mov.l @(36,r4),r0 / rts / nop


class TestEquivReach(unittest.TestCase):
    def setUp(self):
        saved_path = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        modules = dict(sys.modules)
        self.addCleanup(self.restore_modules, modules)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(self.tmp.name)
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import sh4sim
        import equiv
        self.sh4sim, self.equiv = sh4sim, equiv

    @staticmethod
    def restore_modules(modules):
        for name in list(sys.modules):
            if name not in modules:
                del sys.modules[name]

    def call(self, code, callee=READS, junk=None):
        """the one call the code makes, as sh4sim records it (the callee mocked, as the checker runs it)"""
        path = os.path.join(self.tmp.name, '1ST_READ.BIN')
        with open(path, 'wb') as f:
            f.write(code)
        case = {'exe': '1ST_READ.BIN', 'base': '%08X' % BASE, 'entry': '%08X' % BASE, 'end': '%08X' % (BASE + len(code)),
                'poke': {'%08X' % CALLEE: callee.hex()}}
        if junk is not None:                    # what the frame held before, at the field (the stack the run starts on)
            r4 = self.sh4sim.STACK_TOP - 0x100 - 4 - 64
            case['poke']['%08X' % (r4 + FIELD)] = struct.pack('<I', junk).hex()
        result = self.sh4sim.run(case, self.tmp.name)
        self.assertIsNone(result['error'])
        self.assertEqual(len(result['calls']), 1)
        return result['calls'][0]

    def compare(self, a, b):
        view = [('callee', ['STACK'])]          # r4 compared as the stack, as the checker does for a frame address
        return self.equiv.same_bufs([a], [b], view, view)

    def test_reach(self):
        c = self.call(caller(MOV_7_R1, STORE_FIELD))
        self.assertEqual(c['reach'], {'r4': [[FIELD, 7, True]]})
        self.assertEqual(c['bufs'], {'r4': []})     # the old comparison saw nothing: no word stored right at the argument

    def test_differs(self):
        why = self.compare(self.call(caller(MOV_7_R1, STORE_FIELD)), self.call(caller(NOP, NOP)))
        self.assertIn('reads r4+36', why)

    def test_agrees(self):
        self.assertEqual(self.compare(self.call(caller(MOV_7_R1, STORE_FIELD)), self.call(caller(MOV_7_R1, STORE_FIELD))), '')
        self.assertIn('reads r4+36', self.compare(self.call(caller(MOV_7_R1, STORE_FIELD)), self.call(caller(MOV_9_R1, STORE_FIELD))))

    def test_leftover(self):
        a, b = self.call(caller(NOP, NOP), junk=0x11111111), self.call(caller(NOP, NOP), junk=0x22222222)
        self.assertEqual(a['reach'], {'r4': [[FIELD, 0x11111111, False]]})
        self.assertEqual(self.compare(a, b), '')

    def test_written(self):
        self.assertEqual(self.call(caller(MOV_7_R1, STORE_FIELD), callee=WRITES_FIRST)['reach'], {})

    # --- an output over an input ---

    def variants(self, regs, writes, reads, alias=None):
        case = {'regs': regs}
        if alias:
            case['alias'] = alias
        orig = {'writes': [['%08X' % a, 4, '00000000'] for a in writes], 'reads': reads}
        return [(v['alias'], v['regs']) for v in self.equiv.alias_variants(case, orig)]

    def test_variant(self):
        regs = {'r4': '0C800000', 'r5': '0C800100', 'r6': '0C800200'}       # nlOuterProduct(a, b, out)
        got = self.variants(regs, writes=[0x0C800200, 0x0C800204], reads=[0x0C800000, 0x0C800104])
        self.assertEqual(got, [('output r6 over r4', dict(regs, r6='0C800000')), ('output r6 over r5', dict(regs, r6='0C800100'))])

    def test_skip(self):
        regs = {'r4': '0C800000', 'r5': '00000003', 'r6': '0C800000', 'r7': '0C800300'}
        # r4 written and r6 the same address; r5 a value; r7 never read
        self.assertEqual(self.variants(regs, writes=[0x0C800000], reads=[0x0C800000]), [])

    def test_once(self):
        regs = {'r4': '0C800000', 'r5': '0C800100', 'r6': '0C800000'}
        self.assertEqual(self.variants(regs, writes=[0x0C800000], reads=[0x0C800100], alias='output r6 over r4'), [])

    # --- an aliased variant the original cannot run on ---

    def test_variant_the_original_stops_on_has_no_verdict(self):
        aliased = {'regs': {}, 'alias': 'output r6 over r4'}
        self.assertTrue(self.equiv.alias_unusable(aliased, {'error': 'more than 2000000 instructions'}),
                        'the original looped on the aliased input: the case says nothing about the C')
        self.assertTrue(self.equiv.alias_unusable(aliased, {'error': 'unaligned 4-byte read at 0C800001'}))

    def test_variant_the_original_runs_on_is_compared(self):
        self.assertFalse(self.equiv.alias_unusable({'regs': {}, 'alias': 'output r6 over r4'}, {'error': None}))

    def test_a_plain_case_the_original_stops_on_still_fails(self):
        self.assertFalse(self.equiv.alias_unusable({'regs': {}}, {'error': 'more than 2000000 instructions'}),
                         'only an aliased variant is dropped: the original stopping on a real case is still a failure')


if __name__ == '__main__':
    unittest.main()
