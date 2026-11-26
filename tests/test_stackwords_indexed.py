#!/usr/bin/env python3
"""callee_stack_words counts a stack argument read through an index: `mov #k,r0` then `@(r0,r15)`, after the pushes. A register
set again by anything else is no longer a known index. The count lowers what a call is compared on, so what keeps
and what forgets an index, and when no count is given at all, are held down here. No game data. Stdlib only."""
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')
sys.path.insert(0, ROOT)
import toolpath  # noqa: E402,F401
sys.path.insert(0, os.path.join(ROOT, '5-generated', 'gen_equiv'))
sys.path.insert(0, os.path.join(ROOT, '5-generated'))
sys.path.insert(0, os.path.join(ROOT, 'sim'))
# the tool reads the game's files from the current folder when it is imported: stand-ins in a temporary one
_cwd = os.getcwd()
_tmp = tempfile.TemporaryDirectory()
os.chdir(_tmp.name)
with open('1ST_READ.BIN', 'wb') as _f:
    _f.write(b'\x09\x00' * 64)
with open('BASE', 'w') as _f:
    _f.write('8C010000\n')
with open('functions.txt', 'w') as _f:
    _f.write('F 8c010000 128 stubfn\n')
import gen_core  # noqa: E402
import equiv  # noqa: E402
os.chdir(_cwd)


def words(name, lines):
    text = 'header\n\n' + ''.join('8c0000%02x 0000  %s\n' % (2 * i, l) for i, l in enumerate(lines))
    with mock.patch.object(gen_core.subprocess, 'run', return_value=mock.Mock(stdout=text)):
        gen_core._STACKW.pop(name, None)
        return gen_core.callee_stack_words(name)


class Indexed(unittest.TestCase):
    def test_indexed_load_after_pushes(self):
        self.assertEqual(words('a', ['mov.l r14,@-r15', 'mov #12,r0', 'mov.l r13,@-r15', 'mov.l r12,@-r15',
                                     'fmov.s @(r0,r15),fr0', 'rts']), 1)
        self.assertEqual(words('b', ['mov.l r14,@-r15', 'mov #4,r0', 'add #4,r0', 'mov.l @(r0,r15),r1', 'rts']), 2)

    def test_index_overwritten_is_unknown(self):
        self.assertEqual(words('c', ['mov #0,r0', 'mov.l @r4,r0', 'mov.l @(r0,r15),r1', 'rts']), 0)

    def test_own_frame_is_not_an_argument(self):
        self.assertEqual(words('d', ['add #-8,r15', 'mov #4,r0', 'mov.l @(r0,r15),r1', 'rts']), 0)

    def test_direct_and_indexed_loads_take_the_highest_word(self):
        self.assertEqual(words('e', ['mov.l @r15,r1', 'mov #8,r0', 'mov.l @(r0,r15),r2', 'rts']), 3)
        self.assertEqual(words('f', ['mov #0,r0', 'mov.l @(r0,r15),r1', 'mov.l @(8,r15),r2', 'rts']), 3)

    def test_instructions_that_leave_the_index_alone(self):
        for k, keep in enumerate(('cmp/eq #1,r0', 'tst #1,r0', 'mov.l r0,@r4', 'mov.l r1,@r0', 'mov r0,r1', 'add r0,r2',
                                  'fmov.s @(r0,r4),fr1')):
            self.assertEqual(words('g%d' % k, ['mov #4,r0', keep, 'fmov.s @(r0,r15),fr0', 'rts']), 2, keep)

    def test_instructions_that_set_the_index_register_forget_it(self):
        for k, lose in enumerate(('mov r4,r0', 'shll2 r0', 'add r4,r0', 'mov.w @(0x8c000040,pc),r0', 'extu.b r1,r0',
                                  'sts fpul,r0', 'movt r0', 'dt r0')):
            self.assertEqual(words('h%d' % k, ['mov #4,r0', lose, 'mov.l @(r0,r15),r1', 'rts']), 0, lose)

    def test_load_into_the_index_register(self):
        self.assertEqual(words('i', ['mov #4,r0', 'mov.l @(r0,r15),r0', 'mov.l @(r0,r15),r1', 'rts']), 2)

    def test_pushes_between_index_and_load(self):
        self.assertEqual(words('j', ['mov #8,r0', 'mov.l r14,@-r15', 'sts.l pr,@-r15', 'mov.l @(r0,r15),r1', 'rts']), 1)

    def test_unaligned_index_and_code_after_the_return(self):
        self.assertEqual(words('k', ['mov #2,r0', 'mov.l @(r0,r15),r1', 'rts']), 0)
        self.assertEqual(words('l', ['mov.l @r15,r1', 'rts', 'nop', 'mov #12,r0', 'mov.l @(r0,r15),r2']), 1)


class Narrowing(unittest.TestCase):
    def count(self, listing, counted):
        with mock.patch.object(equiv.subprocess, 'run', return_value=mock.Mock(stdout=listing)), \
             mock.patch.object(gen_core, 'callee_stack_words', return_value=counted):
            return equiv._orig_stack_words('f')

    def test_a_pointer_into_the_stack_gives_no_count(self):
        self.assertEqual(self.count('8c000000 0000  mov r15,r4\n', 1), 0)

    def test_plain_and_indexed_loads_give_the_count(self):
        self.assertEqual(self.count('8c000000 0000  fmov.s @(r0,r15),fr0\n', 1), 1)


if __name__ == '__main__':
    unittest.main()
