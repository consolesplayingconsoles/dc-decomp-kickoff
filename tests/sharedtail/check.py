#!/usr/bin/env python3
"""A branch into another function's epilogue is the function's own ending (scripts/tools/sh4sim.py shared_epilogue, the generator's
reading in scripts/tools/5-generated/gen_equiv/gen_core.py). No game data, no compiler. Stdlib only.

The compiler lets a function end by branching into the epilogue of another one: the pops, a constant into r4, a jmp to a callee
(Zombie Revenge FUN_0c0b8bcc -> 0C0B965A, the end of FUN_0c0b954e: nlPopMatrix(1)). The simulator took the branch for a tail call and
returned to a stale pr (the original never finished), and the generator called the epilogue's address through a cast.

    check.py      a callee (rts, returning r4), a function B ending in `mov #1,r4; lds.l @r15+,pr; jmp callee`, and a function A that saves pr and
                  branches to B's `mov #1,r4`:
                    sim       A runs to its return, its last call is the jump to the callee with r4 = 1, the stack balanced
                    written   the generated C of A ends in callee(0x1), not a call to B's epilogue address
"""
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
BASE = 0x0C010000
W = lambda ws: b''.join(struct.pack('<H', w) for w in ws)

CALLEE = [0x000B, 0x6043]                            # rts / mov r4,r0 (it reads r4)
B = [0x4F22,                                         # sts.l pr,@-r15
     0xE401,                                         # mov #1,r4          (the shared epilogue starts here, BASE+6)
     0x4F26,                                         # lds.l @r15+,pr
     0xD201,                                         # mov.l @(pool),r2   (= callee)
     0x422B, 0x0009]                                 # jmp @r2 / nop
A = [0x4F22,                                         # sts.l pr,@-r15
     0xAFF6, 0x0009, 0x0009]                         # bra BASE+6 / nop / (pad)


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        code = W(CALLEE) + W(B) + struct.pack('<I', BASE) + W(A)
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x 4 callee\nF %08x 16 fnb\nF %08x 8 fna\n' % (BASE, BASE + 4, BASE + 0x14))
        os.makedirs(os.path.join(tmp, 'src'))
        case = {'exe': os.path.join(tmp, '1ST_READ.BIN'), 'base': '%08X' % BASE, 'entry': '%08X' % (BASE + 0x14), 'end': '%08X' % (BASE + 0x1C)}
        json.dump(case, open(os.path.join(tmp, 'case.json'), 'w'))
        out = subprocess.run([sys.executable, os.path.join(tmp, 'tools', 'sh4sim.py'), 'run', os.path.join(tmp, 'case.json')],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout
        try:
            r = json.loads(out)
            last = r['calls'][-1] if r['calls'] else {}
            if r['error'] or last.get('to') != '%08X' % BASE or last.get('r4-r7', [''])[0] != '00000001' or not r['r15_balanced']:
                bad.append('sim: %s, calls %s' % (r['error'], r['calls']))
        except ValueError:
            bad.append('sim: %s' % out)
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                  "try:\n"
                  "    print(gen_drv.build('fna', 'r0', False)[0])\n"
                  "except gen_core.Skip as e:\n"
                  "    print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        if 'SKIPPED' in out or 'callee(0x1)' not in out or '0xC010006' in out:
            bad.append('written: the C does not end in callee(0x1):\n%s' % out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] sharedtail check failed:\n' + '\n'.join(bad))
    print('[sharedtail] ok: a branch into another function\'s epilogue is the function\'s own ending')


if __name__ == '__main__':
    main()
