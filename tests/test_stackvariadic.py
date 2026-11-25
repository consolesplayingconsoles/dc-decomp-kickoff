#!/usr/bin/env python3
"""Every word pushed for a call to a callee that takes the address of its stack words stays a call argument
(scripts/tools/5-generated/gen_equiv/gen_core.py, the `own_stack` trim). No game data, no compiler. Stdlib only.

A variadic print (Power Stone 2 FUN_0c187cac, called by FUN_0c012cb8 with a format and one more word) is passed the address of its stack
words, and its code reads only one of them directly. The generator took the words pushed below the one it reads for an earlier call's
deferred words and dropped them, so the C passed five words where the original pushed six.

    check.py      a callee that takes `r15 + 8` as a pointer and reads one stack word, a caller that pushes two words and calls it:
                    words     the call carries r4-r7 and both pushed words
"""
import unittest
from unittest import mock
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

# a variadic print: it takes the address of its stack words (`mov r15,r4 / add #8,r4`) and reads one of them
CALLEE = [0x4F22, 0x6043, 0x64F3, 0x7408, 0x55F1, 0x4F26, 0x000B, 0x0009]    # sts.l pr / mov r4,r0 / mov r15,r4 / add #8,r4 / mov.l @(4,r15),r5 / lds.l @r15+,pr / rts / nop
# the caller pushes two words and calls with r4 set; the callee's own stack word is the last one pushed, the first is a word it
# reaches through its address
CALLER = [0x4F22,                                    # sts.l pr,@-r15
          0xE201, 0xE302,                            # mov #1,r2 / mov #2,r3
          0x2F26, 0x2F36,                            # mov.l r2,@-r15 / mov.l r3,@-r15
          0xBFF1, 0xE404,                            # bsr callee / mov #4,r4 (delay slot)
          0x7F08, 0x4F26, 0x000B, 0x0009]            # add #8,r15 / lds.l @r15+,pr / rts / nop


class TestStackvariadic(unittest.TestCase):
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

    def test_stackvariadic(self):
        bad = []
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
            callee, caller = W(CALLEE), W(CALLER)
            open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(callee + caller)
            open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
            open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d callee\nF %08x %d caller\n'
                                                               % (BASE, len(callee), BASE + len(callee), len(caller)))
            os.makedirs(os.path.join(tmp, 'src'))
            open(os.path.join(tmp, 'src', 'callee.c'), 'w').write(
                'int callee(void)\n{\n    return 5;\n}\n')
            script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                      "try:\n"
                      "    print(gen_drv.build('caller', 'r0', False)[0])\n"
                      "except gen_core.Skip as e:\n"
                      "    print('SKIPPED ' + str(e))\n")
            out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, universal_newlines=True).stdout
            if 'SKIPPED' in out or 'caller' not in out:
                bad.append('written: the generator did not write it:\n%s' % out)
            else:
                m = re.search(r'\bcallee\(([^;]*)\);', out)
                if not m:
                    bad.append('call: no call to callee in the generated C:\n%s' % out)
                else:
                    args = [a.strip() for a in m.group(1).rstrip(')').split(',')]
                    # r4-r7 and both pushed words (1 and 2): six arguments
                    if args != ['0x4', 'a5', 'a6', 'a7', '0x2', '0x1']:
                        bad.append('words: the call carries %d arguments (%s), expected r4-r7 and the two pushed words:\n%s' % (len(args), m.group(1), out))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if bad:
            self.fail('[ERROR] stackvariadic check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
