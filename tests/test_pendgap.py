#!/usr/bin/env python3
"""A word read at SP after a frame was made below pushed words is the frame's, not a pushed one
(scripts/tools/5-generated/gen_equiv/gen_core.py, the reload of a pending push). No game data, no compiler. Stdlib only.

A read at @(d,r15) while pushed words were pending was taken as the push d bytes up, even when an add to r15 had made a frame below
them: a function with a second prologue inside it (registers pushed, then a 28-byte frame) read its own loop counter as a saved
register's value (Zombie Revenge FUN_0c0658f0: a row number came out 0x2C on every pass, from the 0x100 in a pushed r8).

    check.py      a function that pushes r4, makes an 8-byte frame, stores 5 at SP and reads SP back into r0:
                    frame     the C returns 5 (the frame word), not a4 (the pushed word)
                  one listed function holding two: the first body pops its frame and branches into a second prologue that pushes
                  r14 (holding 0x12), makes a frame, stores 5 at SP and reads SP back (Virtua Tennis FUN_8c01219e, generated before
                  this fix: the attract loop read a player's CPU flag from 0x26 + 4i, a CPU opponent paused the exhibition):
                    branch    the C returns 5, not 0x12
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
BASE = 0x0C010000
W = lambda ws: b''.join(struct.pack('<H', w) for w in ws)

FN = [0x4F22,                       # sts.l pr,@-r15
      0xE300,                       # mov #0,r3 (the prologue ends)
      0x2F46,                       # mov.l r4,@-r15
      0x7FF8,                       # add #-8,r15
      0xE105,                       # mov #5,r1
      0x2F12,                       # mov.l r1,@r15
      0x60F2,                       # mov.l @r15,r0
      0x7F0C,                       # add #12,r15
      0x4F26,                       # lds.l @r15+,pr
      0x000B, 0x0009]               # rts / nop

FN2 = [0x2FE6,                      # mov.l r14,@-r15      the first body
       0x4F22,                      # sts.l pr,@-r15
       0xEE12,                      # mov #18,r14
       0x4F26,                      # lds.l @r15+,pr       its epilogue
       0xA000,                      # bra to the second prologue
       0x6EF6,                      #  mov.l @r15+,r14
       0x2FE6,                      # mov.l r14,@-r15      the second prologue: r14 (0x12) pushed
       0x4F22,                      # sts.l pr,@-r15
       0x7FF8,                      # add #-8,r15          a frame below the pushes
       0xE105, 0x2F12,              # mov #5,r1 / mov.l r1,@r15
       0x60F2,                      # mov.l @r15,r0        the frame word, not the push
       0x7F08,                      # add #8,r15
       0x4F26,                      # lds.l @r15+,pr
       0x000B, 0x6EF6]              # rts / mov.l @r15+,r14


def generate(fn):
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        code = W(fn) + (W([0x0009]) if len(fn) % 2 else b'')
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d xform\n' % (BASE, len(code)))
        os.makedirs(os.path.join(tmp, 'src'))
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                  "try:\n"
                  "    print(gen_drv.build('xform', 'r0', False)[0])\n"
                  "except gen_core.Skip as e:\n"
                  "    print('SKIPPED ' + str(e))\n")
        return subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, universal_newlines=True).stdout
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class TestPendgap(unittest.TestCase):
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

    def test_pendgap(self):
        bad = []
        out = generate(FN)
        if 'SKIPPED' in out or 'xform' not in out:
            bad.append('written: the generator did not write it:\n%s' % out)
        elif 'a4' in out.split('{', 1)[1]:
            bad.append('frame: the C reads the pushed a4 back, not the frame word:\n%s' % out)
        out = generate(FN2)
        if 'SKIPPED' in out or 'xform' not in out:
            bad.append('branch: the generator did not write it:\n%s' % out)
        elif 'return 0x5;' not in out:
            bad.append('branch: a second prologue reached by a branch: the C does not return the frame word 5:\n%s' % out)
        if bad:
            self.fail('[ERROR] pendgap check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
