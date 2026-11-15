#!/usr/bin/env python3
"""Arity of a pass-through trampoline whose target is not known (scripts/tools/5-generated/gen_equiv/gen_core.py callee_arity). No game
data, no compiler: shdis is replaced by stand-in disassembly text. Stdlib only.

A trampoline that jumps on with r4-r7 untouched takes the arguments of its target. When the jump is a table jump (the target is read
from memory: gdFsOpenRange and gdFsEntryErrFuncAll jump through the file system's table) the target is not known, and the arity is
unknown. It used to be settled by the function's own definition in src/, a `(void)` the generator wrote for the same reason: callers
were then generated without the arguments the original sets (Virtua Tennis: the drive-error callback never registered, a file range
opened from leftover registers) and the proof compared them on none.

    check.py      table      a table-jump trampoline is unknown (None), whatever its (void) definition says, and the scan file
                             says why ("pass-through"), a null rescans
                  named      a jump to a named function takes that function's arity
                  defonly    a function that is not a pass-through still takes its definition's arity when its code reads less
                  delay      an argument read in the delay slot of the function's first call counts (Zombie Revenge ADXT_Stop: called with no handle)
"""
import unittest
from unittest import mock
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')
GEN = os.path.join(TOOLS, '5-generated', 'gen_equiv')
sys.path[:0] = [GEN, os.path.join(GEN, '..'), TOOLS]

TABLE = """; gdFsOpenRange 8c1de7e0, 24 bytes (functions.txt)

gdFsOpenRange:
8c1de7e0 d344  mov.l @(0x8c1de8f4,pc),r3  ; =8c20c210 g_8c20c210
8c1de7e2 2fe6  mov.l r14,@-r15
8c1de7e4 6e32  mov.l @r3,r14
8c1de7e6 2ee8  tst r14,r14
8c1de7e8 8903  bt 0x8c1de7f2
8c1de7ea e044  mov #68,r0
8c1de7ec 00ee  mov.l @(r0,r14),r0
8c1de7ee 402b  jmp @r0
8c1de7f0 6ef6  mov.l @r15+,r14
8c1de7f2 e000  mov #0,r0
8c1de7f4 000b  rts
8c1de7f6 6ef6  mov.l @r15+,r14
"""
NAMED = """; wrapperA 8c1de000, 8 bytes (functions.txt)

wrapperA:
8c1de000 d101  mov.l @(0x8c1de008,pc),r1  ; =8c1de100 targetB
8c1de002 412b  jmp @r1
8c1de004 0009  nop
"""
DELAY = """; delayReads 8c1de300, 12 bytes (functions.txt)

delayReads:
8c1de2fe d301  mov.l @(0x8c1de308,pc),r3  ; =8c1de400 targetZero
8c1de300 430b  jsr @r3
8c1de302 6e43  mov r4,r14
8c1de304 000b  rts
8c1de306 0009  nop
"""
ZERO = """; targetZero 8c1de400, 4 bytes (functions.txt)

targetZero:
8c1de400 000b  rts
8c1de402 0009  nop
"""
READS = """; readsLess 8c1de200, 8 bytes (functions.txt)

readsLess:
8c1de200 6043  mov r4,r0
8c1de202 000b  rts
8c1de204 0009  nop
"""


class TestArity(unittest.TestCase):
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

    def test_arity(self):
        os.chdir(tempfile.mkdtemp())
        open('1ST_READ.BIN', 'wb').write(b'\x09\x00' * 64)
        open('BASE', 'w').write('8C010000\n')
        open('functions.txt', 'w').write('F 8c010000 128 stubfn\n')
        import gen_core
        for n, a, z in (('gdFsOpenRange', 0x8C1DE7E0, 24), ('wrapperA', 0x8C1DE000, 8), ('readsLess', 0x8C1DE200, 8), ('targetB', 0x8C1DE100, 8), ('delayReads', 0x8C1DE2FE, 400), ('targetZero', 0x8C1DE400, 4)):
            gen_core.SPANS[n] = (a, z)                 # the sizes functions.txt gives: a pass-through is a few bytes
        bad = []
        text = {'gdFsOpenRange': TABLE, 'wrapperA': NAMED, 'readsLess': READS, 'delayReads': DELAY, 'targetZero': ZERO,
                'targetB': READS.replace('readsLess', 'targetB')}

        class R:
            def __init__(self, out): self.stdout = out

        patcher = mock.patch.object(gen_core.subprocess, 'run', lambda cmd, **kw: R(text[cmd[-1]]))
        patcher.start()
        self.addCleanup(patcher.stop)
        gen_core._DEFS = {'gdFsOpenRange': (0, 0), 'wrapperA': (0, 0), 'readsLess': (3, 0)}      # the generated definitions

        got = gen_core.callee_arity('gdFsOpenRange')
        if got is not None:
            bad.append('table: a table-jump trampoline takes %s, want unknown (None), not its (void) definition' % (got,))
        scan = json.load(open(os.path.join('state', 'arity_scan.json')))
        if scan.get('gdFsOpenRange') != getattr(gen_core, 'UNRESOLVED_PT', 'pass-through'):
            bad.append('table: arity_scan.json says %r, want %r' % (scan.get('gdFsOpenRange'), getattr(gen_core, 'UNRESOLVED_PT', 'pass-through')))
        gen_core._ARITY.clear()
        if gen_core.callee_arity('gdFsOpenRange') is not None:
            bad.append('table: the second call (from the scan file) is not unknown')
        json.dump({'oldNull': None}, open(os.path.join('state', 'arity_scan.json'), 'w'))
        if 'oldNull' in {k: v for k, v in json.load(open(os.path.join('state', 'arity_scan.json'))).items() if v is not None}:
            bad.append('table: a null in the scan file is kept')

        got = gen_core.callee_arity('delayReads')
        if got != (1, 0):
            bad.append('delay: r4 read in the delay slot of the first call is an argument (the slot runs before the call), got %s, want (1, 0)' % (got,))

        gen_core.SPANS['helperThenRead'] = (0x8C1DE600, 100)
        text['helperThenRead'] = '\n'.join(['; helperThenRead', '', '8c1de600 4f22  sts.l pr,@-r15', '8c1de602 d322  mov.l @(0x8c1de690,pc),r3  ; =8c0e609c _quick_evn_mvn',
            '8c1de604 61f3  mov r15,r1', '8c1de606 430b  jsr @r3', '8c1de608 e030  mov #48,r0', '8c1de60a 6641  mov.w @r4,r6', '8c1de60c 2502  mov.l r0,@r5',
            '8c1de60e 4f26  lds.l @r15+,pr', '8c1de610 000b  rts', '8c1de612 0009  nop'])
        got = gen_core.callee_arity('helperThenRead')
        if got != (2, 0):
            bad.append('helper: r4 and r5 read after a call to a runtime helper (it works in r0-r3) are arguments, got %s, want (2, 0)' % (got,))
        gen_core.SPANS['helperSaves'] = (0x8C1DE700, 100)
        gen_core.SPANS['_quick_evn_mvn'] = (0x8C0E609C, 40)
        text['_quick_evn_mvn'] = '\n'.join(['; _quick_evn_mvn', '', '8c0e609c 2f46  mov.l r4,@-r15', '8c0e609e 2f56  mov.l r5,@-r15', '8c0e60a0 2f66  mov.l r6,@-r15',
            '8c0e60a2 66f6  mov.l @r15+,r6', '8c0e60a4 000b  rts', '8c0e60a6 0009  nop'])
        text['helperSaves'] = text['helperThenRead'].replace('helperThenRead', 'helperSaves').replace('8c1de60c 2502  mov.l r0,@r5', '8c1de60c 0009  nop')
        got = gen_core.callee_arity('helperSaves')
        if got != (1, 0):
            bad.append('helper: a runtime helper that saves r4-r6 does not make them arguments of its caller, got %s, want (1, 0): only the r4 read after it' % (got,))
        gen_core.SPANS['ctxSave'] = (0x8C1DE800, 100)
        text['ctxSave'] = '\n'.join(['; ctxSave', '', '8c1de800 1479  mov.l r7,@(36,r4)', '8c1de802 145b  mov.l r5,@(44,r4)', '8c1de804 1413  mov.l r1,@(12,r4)',
            '8c1de806 f44b  fmov.s fr4,@-r4', '8c1de808 000b  rts', '8c1de80a e000  mov #0,r0'])
        got = gen_core.callee_arity('ctxSave')
        if got != (1, 0):
            bad.append('context save: a routine that stores every register (r1 as it came in among them) through r4 takes %s, want (1, 0)' % (got,))
        for nm, z in (('afterKeep', 100), ('afterClob', 100), ('keepfn', 8), ('clobfn', 8)):
            gen_core.SPANS[nm] = (0x8C1DE900, z)
        body = lambda who, callee: '\n'.join(['; ' + who, '', '8c1de900 4f22  sts.l pr,@-r15', '8c1de902 d322  mov.l @(0x8c1de990,pc),r3  ; =8c1dea00 ' + callee,
            '8c1de904 430b  jsr @r3', '8c1de906 0009  nop', '8c1de908 6141  mov.w @r4,r1', '8c1de90a 2512  mov.l r1,@r5', '8c1de90c 4f26  lds.l @r15+,pr', '8c1de90e 000b  rts', '8c1de910 0009  nop'])
        text['afterKeep'], text['afterClob'] = body('afterKeep', 'keepfn'), body('afterClob', 'clobfn')
        text['keepfn'] = '\n'.join(['; keepfn', '', '8c1dea00 0002  stc sr,r0', '8c1dea02 000b  rts', '8c1dea04 0009  nop'])
        text['clobfn'] = '\n'.join(['; clobfn', '', '8c1dea00 e401  mov #1,r4', '8c1dea02 000b  rts', '8c1dea04 0009  nop'])
        got = gen_core.callee_arity('afterKeep')
        if got != (2, 0):
            bad.append('keeps: r4 and r5 read after a call to a leaf that writes none of r4-r7 are arguments, got %s, want (2, 0)' % (got,))
        got = gen_core.callee_arity('afterClob')
        if got != (0, 0):
            bad.append('keeps: after a call to a routine that writes r4 the arguments are gone, got %s, want (0, 0)' % (got,))
        # a call on a side branch before the arguments are read: the straight scan sees the call first; the code's liveness (entry_reads) decides
        gen_core.SPANS['sideCall'] = (0x8C1DEB00, 100)
        text['sideCall'] = body('sideCall', 'clobfn')
        gen_core._ENTRY['sideCall'] = frozenset(['r4', 'r5'])
        got = gen_core.callee_arity('sideCall')
        if got != (2, 0):
            bad.append('side call: the arguments the code reads on some path count though a call comes first in address order, got %s, want (2, 0)' % (got,))
        got = gen_core.callee_arity('readsLess')
        if got != (3, 0):
            bad.append('defonly: a function reading 1 register with a 3-parameter definition takes %s, want (3, 0)' % (got,))
        if bad:
            self.fail('[ERROR] arity check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    unittest.main()
