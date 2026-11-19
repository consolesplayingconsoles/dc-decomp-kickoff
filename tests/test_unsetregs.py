#!/usr/bin/env python3
"""A drawn case whose outcome depends on registers the function never set (scripts/tools/5-generated/gen_equiv/directed.py
unset_dependent), with the real simulator on synthetic code. No game data, no compiler. Stdlib only.

Virtua Tennis shopDrawCatPanel picks an index from a4 by a chain of compares (1, 6, 2, 0, 4, 5) into r10 and leaves r10 untouched for
any other a4: the original then indexes with the caller's r10, the C with an uninitialised variable. A case drawn with such an a4 is
no input the game makes, and the two sides read different words. unset_dependent runs the original twice with different incoming
r8-r14: when what it does differs, the case depends on them and is dropped.

    check.py      reads    stores the incoming r10 to memory: dependent
                  sets     sets r10 first, then stores it: not dependent
                  freads   stores the incoming fr12: dependent
                  fcall    passes the incoming fr12 to a call as fr4 (endingSceneDraw, Virtua Tennis: fr12 set on other paths only):
                           dependent
                  aftercall  stores r5 after a call (a caller-saved register the callee may change: entryGridDrawCursors, Virtua
                           Tennis, a colour from r5 after mathLerp on a path that never sets it): dependent
                  result   stores r0 after a call (the call's result): not dependent
                  leftarg  calls a function after another call without setting r6, r7 or a float register: what is in them is the
                           first callee's leftover, not an argument. Told the callee takes two integers and no float (argc, fargc),
                           the case is not dependent; told nothing, every argument register counts, as before
"""
import unittest
from unittest import mock
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')
sys.path[:0] = [os.path.join(TOOLS, '5-generated', 'gen_equiv'), os.path.join(TOOLS, '5-generated'), TOOLS]
import toolpath  # noqa: E402,F401
import sh4sim  # noqa: E402
import directed  # noqa: E402

BASE = 0x8C010000


class TestUnsetregs(unittest.TestCase):
    def setUp(self):
        self.addCleanup(os.chdir, os.getcwd())
        saved_path = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved_path)
        environ = mock.patch.dict(os.environ)
        environ.start()
        self.addCleanup(environ.stop)
        snapshot = self._snapshot_modules()
        self.addCleanup(self._restore_modules, snapshot)

    @staticmethod
    def _snapshot_modules():
        tools = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts')
        modules = dict(sys.modules)
        state = {}
        for name, mod in modules.items():
            if (getattr(mod, '__file__', None) or '').startswith(tools):
                state[name] = dict(vars(mod))
        return modules, state

    @staticmethod
    def _restore_modules(snapshot):
        modules, state = snapshot
        for name in list(sys.modules):
            if name not in modules:
                del sys.modules[name]
        sys.modules.update(modules)
        for name, saved in state.items():
            vars(modules[name]).clear()
            vars(modules[name]).update(saved)

    def test_unsetregs(self):
        bad = []
        d = tempfile.mkdtemp()
        try:
            for name, first, store, want in (('reads', 0x0009, 0x21A2, True), ('sets', 0xEA05, 0x21A2, False), ('freads', 0x0009, 0xF1CA, True)):
                code = [first,               # nop, or mov #5,r10
                        0xD102,              # mov.l @(pool),r1
                        store,               # mov.l r10,@r1 / fmov.s fr12,@r1
                        0x000B, 0x0009,      # rts / nop
                        0x0009]
                body = b''.join(struct.pack('<H', w) for w in code) + struct.pack('<I', BASE + 0x100)
                open(os.path.join(d, name + '.bin'), 'wb').write(body + b'\x00' * (0x200 - len(body)))
                run = lambda c, n=name: sh4sim.run(dict(c, exe=n + '.bin', base='%08X' % BASE, entry='%08X' % BASE, end='%08X' % (BASE + 0xA),
                                                        steps=2000), d)
                try:
                    got = directed.unset_dependent({}, run)
                except AttributeError:
                    self.fail('[ERROR] unsetregs check failed:\ndirected.py has no unset_dependent()')
                if got != want:
                    bad.append('%s: dependent %s, want %s' % (name, got, want))
            code = [0x4F22, 0xF4CC,      # sts.l pr / fmov fr12,fr4
                    0xB003, 0x0009,      # bsr f / nop
                    0x4F26, 0x000B, 0x0009,      # lds.l @r15+,pr / rts / nop
                    0x000B, 0x0009]      # f: rts / nop
            body = b''.join(struct.pack('<H', w) for w in code)
            open(os.path.join(d, 'fcall.bin'), 'wb').write(body + b'\x00' * (0x200 - len(body)))
            run = lambda c: sh4sim.run(dict(c, exe='fcall.bin', base='%08X' % BASE, entry='%08X' % BASE, end='%08X' % (BASE + 0xE), steps=2000), d)
            if not directed.unset_dependent({}, run):
                bad.append('fcall: a call given the incoming fr12 is not dependent')
            for name, reg, want in (('aftercall', 5, True), ('result', 0, False)):
                code = [0x4F22, 0xE509,      # sts.l pr / mov #9,r5
                        0xB005, 0x0009,      # bsr f / nop
                        0xD103,              # mov.l @(pool),r1
                        0x2102 | (reg << 4), # mov.l rN,@r1
                        0x4F26, 0x000B, 0x0009,      # lds.l @r15+,pr / rts / nop
                        0x000B, 0x0009,      # f: rts / nop
                        0x0009]
                body = b''.join(struct.pack('<H', w) for w in code) + struct.pack('<I', BASE + 0x100)
                open(os.path.join(d, name + '.bin'), 'wb').write(body + b'\x00' * (0x200 - len(body)))
                run = lambda c, n=name: sh4sim.run(dict(c, exe=n + '.bin', base='%08X' % BASE, entry='%08X' % BASE, end='%08X' % (BASE + 0x12),
                                                        steps=2000), d)
                for case in ({'calls': [{'r0': '00000007'}]}, {}):          # with an answer, and with none (each call then returns 0)
                    got = directed.unset_dependent(case, run)
                    if got != want:
                        bad.append('%s%s: dependent %s, want %s' % (name, '' if case else ' (no answers)', got, want))
            # directed cases pass the same checks (directed.acceptable): a run reaching memory outside RAM is no input for a function whose
            # own cases touch no hardware (playerStartReactions, Virtua Tennis: a directed r4 of 4E6E6B28 read wild addresses, the C's loads
            # in another order); one that depends on registers never set is not either
            run = lambda c, n='reads': sh4sim.run(dict(c, exe=n + '.bin', base='%08X' % BASE, entry='%08X' % BASE, end='%08X' % (BASE + 0xA),
                                                       steps=2000), d)
            try:
                dev = {'devices': [['r', '016208F4', 4, '00000000']]}
                sets_run = lambda c: run(c, 'sets')
                for name_, args_, runner, want_ in (('wild', (dev, False), sets_run, False), ('hardware', (dev, True), sets_run, True),
                                                    ('dependent', ({}, False), run, False)):
                    got_ = directed.acceptable({}, args_[0], args_[1], runner)
                    if got_ != want_:
                        bad.append('acceptable %s: %s, want %s' % (name_, got_, want_))
            except AttributeError:
                bad.append('acceptable: directed.py has no acceptable()')
        finally:
            shutil.rmtree(d, ignore_errors=True)
        if bad:
            self.fail('[ERROR] unsetregs check failed:\n' + '\n'.join(bad))

    @staticmethod
    def _two_calls(d):
        """sts.l pr / bsr g / mov #1,r4 / mov #2,r5 / bsr f / mov #3,r4 / lds.l @r15+,pr / rts / nop / nop / g: rts / nop / f: rts / nop:
        f is called with r4 and r5 set, and with r6, r7 and the float registers as g left them."""
        code = [0x4F22, 0xB007, 0xE401, 0xE502, 0xB006, 0xE403, 0x4F26, 0x000B, 0x0009, 0x0009,
                0x000B, 0x0009,      # g
                0x000B, 0x0009]      # f
        body = b''.join(struct.pack('<H', w) for w in code)
        with open(os.path.join(d, 'leftarg.bin'), 'wb') as fp:
            fp.write(body + b'\x00' * (0x200 - len(body)))
        return lambda c: sh4sim.run(dict(c, exe='leftarg.bin', base='%08X' % BASE, entry='%08X' % BASE, end='%08X' % (BASE + 0x14), steps=2000), d)

    def test_leftover_argument_registers_are_not_a_dependence(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._two_calls(d)
            self.assertEqual([c['to'] for c in run({})['calls']], ['%08X' % (BASE + 0x14), '%08X' % (BASE + 0x18)],
                             'the synthetic function calls g, then f')
            self.assertFalse(directed.unset_dependent({}, run, argc=lambda target: 2, fargc=lambda target: 0),
                             'a callee that takes two integers and no float does not make the case depend on what r6, r7 and fr4-fr11 hold')

    def test_argument_register_the_callee_takes_is_still_a_dependence(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._two_calls(d)
            self.assertTrue(directed.unset_dependent({}, run, argc=lambda target: 4, fargc=lambda target: 0),
                            'a callee that takes four integers is handed a leftover in r6 and r7: the case depends on it')

    def test_float_argument_the_callee_takes_is_still_a_dependence(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._two_calls(d)
            self.assertTrue(directed.unset_dependent({}, run, argc=lambda target: 2, fargc=lambda target: 1),
                            'a callee that takes one float is handed a leftover in fr4: the case depends on it')

    def test_unknown_argument_count_compares_every_register(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._two_calls(d)
            self.assertTrue(directed.unset_dependent({}, run), 'with no argument counts every one of r4-r7 and fr4-fr11 is compared')
            self.assertTrue(directed.unset_dependent({}, run, argc=lambda target: None, fargc=lambda target: 0),
                            'a callee whose integer count is not known keeps all of r4-r7')
            self.assertTrue(directed.unset_dependent({}, run, argc=lambda target: 2, fargc=lambda target: None),
                            'a callee whose float count is not known keeps all of fr4-fr11')

    def test_argument_registers_given_as_a_set(self):
        with tempfile.TemporaryDirectory() as d:
            run = self._two_calls(d)
            none = lambda target: 0
            self.assertFalse(directed.unset_dependent({}, run, argc=lambda target: frozenset((4, 5)), fargc=none), 'the callee reads r4 and r5 only')
            self.assertTrue(directed.unset_dependent({}, run, argc=lambda target: frozenset((4, 6)), fargc=none), 'the callee reads r6, a leftover')


if __name__ == '__main__':
    unittest.main()
