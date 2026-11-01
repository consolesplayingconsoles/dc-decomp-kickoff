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
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
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
READS = """; readsLess 8c1de200, 8 bytes (functions.txt)

readsLess:
8c1de200 6043  mov r4,r0
8c1de202 000b  rts
8c1de204 0009  nop
"""


def main():
    os.chdir(tempfile.mkdtemp())
    open('1ST_READ.BIN', 'wb').write(b'\x09\x00' * 64)
    open('BASE', 'w').write('8C010000\n')
    open('functions.txt', 'w').write('F 8c010000 128 stubfn\n')
    import gen_core
    for n, a, z in (('gdFsOpenRange', 0x8C1DE7E0, 24), ('wrapperA', 0x8C1DE000, 8), ('readsLess', 0x8C1DE200, 8), ('targetB', 0x8C1DE100, 8)):
        gen_core.SPANS[n] = (a, z)                 # the sizes functions.txt gives: a pass-through is a few bytes
    bad = []
    text = {'gdFsOpenRange': TABLE, 'wrapperA': NAMED, 'readsLess': READS,
            'targetB': READS.replace('readsLess', 'targetB')}

    class R:
        def __init__(self, out): self.stdout = out

    gen_core.subprocess.run = lambda cmd, **kw: R(text[cmd[-1]])
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

    got = gen_core.callee_arity('readsLess')
    if got != (3, 0):
        bad.append('defonly: a function reading 1 register with a 3-parameter definition takes %s, want (3, 0)' % (got,))
    if bad:
        sys.exit('[ERROR] arity check failed:\n' + '\n'.join(bad))
    print('arity: ok')


main()
