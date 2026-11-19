#!/usr/bin/env python3
"""The result register of a function that ends in a tail call is its target's (scripts/tools/8-build/retcheck.py tail_returns_in,
scripts/tools/5-generated/gen_equiv/gen_pipe.py variants). The function itself writes no result before a return of its own: the
jump hands the caller whatever the last function of the chain returns, so a float chain must be written `float`, or its callers
read a value the C never returned. No game data, no compiler: a synthetic executable of small functions. Stdlib only.

    leaf_f   fldi1 fr1 ; fmov fr1,fr0 ; rts ; nop       returns in fr0
    leaf_i   mov #1,r0 ; rts ; nop                      returns in r0
    mid_f    bra leaf_f ; nop                           a tail call: fr0, through one jump
    top_f    bra mid_f ; nop                            fr0, through two jumps
    top_i    bra leaf_i ; nop                           r0
    ring_a   bra ring_b ; nop   ring_b: bra ring_a      a chain that never reaches a return says nothing, and ends
    both     bt +2 ; bra leaf_f ; nop ; bra leaf_i ; nop    two targets that disagree say nothing
"""
import unittest
from unittest import mock
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
SLOT = 0x20                                   # every function gets 0x20 bytes
ORDER = ['leaf_f', 'leaf_i', 'mid_f', 'top_f', 'top_i', 'ring_a', 'ring_b', 'both']
ADDR = {n: BASE + i * SLOT for i, n in enumerate(ORDER)}


def bra(at, to):
    return 0xA000 | (((to - (at + 4)) >> 1) & 0xFFF)


def image():
    code = {
        'leaf_f': [0xF19D, 0xF01C, RTS, NOP],
        'leaf_i': [0xE001, RTS, NOP],
        'mid_f': [bra(ADDR['mid_f'], ADDR['leaf_f']), NOP],
        'top_f': [bra(ADDR['top_f'], ADDR['mid_f']), NOP],
        'top_i': [bra(ADDR['top_i'], ADDR['leaf_i']), NOP],
        'ring_a': [bra(ADDR['ring_a'], ADDR['ring_b']), NOP],
        'ring_b': [bra(ADDR['ring_b'], ADDR['ring_a']), NOP],
        'both': [0x8901, bra(ADDR['both'] + 2, ADDR['leaf_f']), NOP, bra(ADDR['both'] + 6, ADDR['leaf_i']), NOP],
    }
    out, sizes = b'', {}
    for n in ORDER:
        body = b''.join(struct.pack('<H', w) for w in code[n])
        sizes[n] = len(body)
        out += body + struct.pack('<H', NOP) * ((SLOT - len(body)) // 2)
    return out, sizes


def repo(tmp, tools=False):
    data, sizes = image()
    open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(data)
    open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
    open(os.path.join(tmp, 'functions.txt'), 'w').write(''.join('F %08x %d %s\n' % (ADDR[n], sizes[n], n) for n in ORDER))
    for d in ('src', 'tests', 'build'):
        os.makedirs(os.path.join(tmp, d))
    if tools:
        shutil.copytree(TOOLS, os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
    return sizes


class TestTailReturnRegister(unittest.TestCase):
    """retcheck.tail_returns_in: the register at the end of a chain of tail calls."""

    def setUp(self):
        self.addCleanup(os.chdir, os.getcwd())
        saved_path = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        environ = mock.patch.dict(os.environ)
        environ.start()
        self.addCleanup(environ.stop)
        saved_modules = dict(sys.modules)
        self.addCleanup(self._restore_modules, saved_modules)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.sizes = repo(tmp.name)
        os.chdir(tmp.name)
        sys.path[:0] = [os.path.join(TOOLS, '8-build'), TOOLS]
        for name in ('retcheck', 'boundaries', 'shdis', 'toolpath'):      # read in this temp repo, not where another test left them
            sys.modules.pop(name, None)
        import retcheck
        self.retcheck = retcheck
        self.spans = {n: (ADDR[n], self.sizes[n]) for n in ORDER}

    @staticmethod
    def _restore_modules(saved):
        for name in list(sys.modules):
            if name not in saved:
                del sys.modules[name]
        sys.modules.update(saved)

    def reg(self, name):
        if not hasattr(self.retcheck, 'tail_returns_in'):
            self.fail('retcheck.py has no tail_returns_in()')
        return self.retcheck.tail_returns_in(ADDR[name], self.sizes[name], self.spans)

    def test_function_with_its_own_return_keeps_its_register(self):
        self.assertEqual(self.reg('leaf_f'), 'fr0', 'a function that writes fr0 before its rts returns in fr0')
        self.assertEqual(self.reg('leaf_i'), 'r0', 'a function that writes r0 before its rts returns in r0')

    def test_tail_call_takes_the_target_register(self):
        self.assertEqual(self.reg('mid_f'), 'fr0', 'a tail call into a float function returns in fr0')
        self.assertEqual(self.reg('top_i'), 'r0', 'a tail call into an int function returns in r0')

    def test_chain_of_tail_calls_is_followed_to_its_end(self):
        self.assertEqual(self.reg('top_f'), 'fr0', 'two tail calls deep, the result is still the last function\'s')

    def test_chain_without_a_return_says_nothing(self):
        self.assertIsNone(self.reg('ring_a'), 'two functions that jump to each other have no result register (and the search ends)')

    def test_targets_that_disagree_say_nothing(self):
        self.assertIsNone(self.reg('both'), 'tail calls into a float and an int function: no single register')

    def test_returns_in_itself_is_unchanged(self):
        self.assertIsNone(self.retcheck.returns_in(ADDR['mid_f'], self.sizes['mid_f']),
                          'returns_in reads the function\'s own code only: a tail call still says nothing there')


class TestTailCallVariants(unittest.TestCase):
    """gen_pipe.variants: the result kinds the generator tries for a function that ends in a tail call, in order."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        repo(cls.tmp.name, tools=True)
        script = ("import sys; sys.path[:0] = ['tools', 'tools/5-generated/gen_equiv']; import toolpath, gen_core, gen_drv, gen_pipe\n"
                  "for n in sys.argv[1:]:\n"
                  "    try:\n"
                  "        v = gen_pipe.variants(n, False); print(n, 'VARIANTS', ' '.join(v))\n"
                  "        for kind in v:\n"
                  "            s, c = gen_drv.build(n, kind, False)\n"
                  "            print('@@@@ %s %s' % (n, kind)); print(gen_drv.protos_text(c.protos)); print(s)\n"
                  "    except Exception as e: print(n, 'ERROR', type(e).__name__, e)\n")
        cls.out = subprocess.run([sys.executable, '-c', script, 'mid_f', 'top_f', 'top_i'], cwd=cls.tmp.name, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, universal_newlines=True).stdout

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def variants(self, name):
        for line in self.out.splitlines():
            if line.startswith(name + ' VARIANTS'):
                return line.split()[2:]
        self.fail('no variants printed for %s: %s' % (name, self.out.strip()[-400:]))

    def text(self, name, kind):
        """The C the generator wrote for the function as that result kind."""
        parts = self.out.split('@@@@ %s %s\n' % (name, kind))
        if len(parts) < 2:
            self.fail('no %s text printed for %s: %s' % (kind, name, self.out.strip()[-400:]))
        return parts[1].split('@@@@ ')[0]

    def test_float_text_declares_the_target_float(self):
        c = self.text('mid_f', 'fr0')
        self.assertIn('float mid_f(', c, 'the function itself is written float')
        self.assertIn('float leaf_f(', c, 'the function it jumps into is declared float: declared int, its result would be converted')
        self.assertNotIn('int leaf_f(', c, 'no int declaration of the float target is left')

    def test_int_text_keeps_the_target_int(self):
        self.assertIn('int leaf_i(', self.text('top_i', 'r0'), 'a tail call written as returning an int declares its target int')

    def test_void_text_after_the_float_one_keeps_the_target_int(self):
        self.assertNotIn('float leaf_f(', self.text('mid_f', 'void'), 'the float declaration belongs to the float text only')

    def test_float_target_is_tried_first(self):
        self.assertEqual(self.variants('mid_f')[0], 'fr0', 'a tail call into a float function is first written as returning a float')

    def test_float_chain_is_tried_first(self):
        self.assertEqual(self.variants('top_f')[0], 'fr0', 'a chain of tail calls ending in a float function is first written as float')

    def test_void_stays_as_a_fallback(self):
        self.assertIn('void', self.variants('mid_f'), 'the void variant is still tried when the float one does not pass')

    def test_int_target_gets_no_float_variant(self):
        self.assertNotIn('fr0', self.variants('top_i'), 'a tail call into an int function is never written as float')


if __name__ == '__main__':
    unittest.main()
