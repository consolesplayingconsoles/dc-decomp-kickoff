#!/usr/bin/env python3
"""A word the caller stored in its frame before the pushes, reached by the pointer a variadic call is given, is a call argument too
(scripts/tools/5-generated/gen_equiv/gen_core.py, after the pushed words of the call). No game data, no compiler. Stdlib only.

Power Stone 2 FUN_0c03e46a stores a4 at @r15, pushes two words and calls a variadic print (FUN_0c187cac) with r15+12 as its pointer: the
original passes seven words, the third stack word being the stored a4; the generated C passed six.

    check.py      a callee that takes `r15 + 8` as a pointer and reads one stack word; a caller that stores r4 at @r15, pushes two words and
                  passes r15+12:
                    frameword the call carries r4-r7, both pushed words and the stored frame word, the last

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

CALLEE = [0x4F22, 0x6043, 0x64F3, 0x7408, 0x55F1, 0x4F26, 0x000B, 0x0009]    # sts.l pr / mov r4,r0 / mov r15,r4 / add #8,r4 / mov.l @(4,r15),r5 / lds.l @r15+,pr / rts / nop
CALLER = [0x4F22, 0x7FFC,                            # sts.l pr,@-r15 / add #-4,r15
          0x2F42,                                    # mov.l r4,@r15 (the frame word)
          0xE201, 0xE302, 0x2F26, 0x2F36,            # mov #1,r2 / mov #2,r3 / push r2 / push r3
          0x64F3, 0x740C,                            # mov r15,r4 / add #12,r4 (the pointer: past the stored word)
          0xBFED, 0x0009,                            # bsr callee / nop
          0x7F08, 0x7F04, 0x4F26, 0x000B, 0x0009]    # add #8,r15 / add #4,r15 / lds.l @r15+,pr / rts / nop


class TestFramewordVariadic(unittest.TestCase):
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

    def test_frameword_variadic(self):
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
                    st = re.search(r'\(\(int\)stk \+ (\d+)\)\) = a4;', out) or re.search(r'stk \+ (\d+)\)+ = a4;', out)
                    last = args[-1]
                    # r4-r7, both pushed words (2, 1), then the stored word: a4 itself or the frame word it was stored in
                    if len(args) != 7 or args[4:6] != ['0x2', '0x1'] or not (last == 'a4' or (st and 'stk' in last and sum(int(x) for x in re.findall(r'\+ (\d+)', last)) == int(st.group(1)))):
                        bad.append('frameword: the call carries %d arguments (%s), expected r4-r7, both pushed words and the stored frame word:\n%s' % (len(args), m.group(1), out))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        if bad:
            self.fail('[ERROR] frameword_variadic check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
