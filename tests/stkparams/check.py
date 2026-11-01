#!/usr/bin/env python3
"""The caller's stack words have one name in the whole function: the one the parameter list gives them
(scripts/tools/5-generated/gen_equiv/gen_drv.py). No game data, no compiler. Stdlib only.

The words were renamed to s.w[i] early, when a first count made them one structure, and the return line was added after that: two
ways for the body and the parameter list to disagree, and the C did not compile.

    check.py      two functions that read the caller's words at SP+8 and SP+16 as floats (fmov.s @(r0,r15)):
                    ret      the sum is returned: the parameters are int a4, Stk3 s, and the return line reads s.w[0], s.w[2] (it read
                             a8, a10)
                    stmt     the sum is also stored in the frame, which keeps an address into the caller's area: the parameters are
                             a4..a10, and the statement reads a8, a10 (it read s.w[0], s.w[2]: Virtua Tennis FUN_8c07fd10)
"""
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
BASE = 0x0C010000
W = lambda ws: b''.join(struct.pack('<H', w) for w in ws)

# add #-8,r15 / mov.l r4,@r15 / mov #8,r0 / fmov.s @(r0,r15),fr0 / mov #16,r0 / fmov.s @(r0,r15),fr1 / fadd fr1,fr0 / ...
HEAD = [0x7FF8, 0x2F42, 0xE008, 0xF0F6, 0xE010, 0xF1F6, 0xF010]
RET = HEAD + [0x62F2, 0x1F21, 0x7F08, 0x000B, 0x0009]                       # mov.l @r15,r2 / mov.l r2,@(4,r15) / add #8,r15 / rts / nop
STMT = HEAD + [0xE004, 0xFF07, 0x63F3, 0x7308, 0x1F31, 0x7F08, 0x000B, 0x0009]  # fmov.s fr0,@(r0,r15) / mov r15,r3 / add #8,r3 / mov.l r3,@(4,r15) / ...


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        data, lines = b'', []
        for name, ws in (('retfn', RET), ('stmtfn', STMT)):
            code = W(ws) + (W([0x0009]) if len(ws) % 2 else b'')
            lines.append('F %08x %d %s' % (BASE + len(data), len(code), name))
            data += code
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(data)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('\n'.join(lines) + '\n')
        os.makedirs(os.path.join(tmp, 'src'))
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                  "for n in sys.argv[1:]:\n"
                  "    try:\n"
                  "        print('@@@@ ' + n); print(gen_drv.build(n, 'fr0', False)[0])\n"
                  "    except gen_core.Skip as e:\n"
                  "        print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script, 'retfn', 'stmtfn'], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        parts = dict(p.split('\n', 1) for p in out.split('@@@@ ')[1:])
        for name in ('retfn', 'stmtfn'):
            c = parts.get(name, '')
            head = c.split('\n', 1)[0]
            body = c.split('{', 1)[1] if '{' in c else ''
            if 'Stk' in head:
                if re.search(r'\ba(8|9|1\d)\b', body):
                    bad.append('%s: Stk parameter, but the body reads a8..:\n%s' % (name, c))
            elif 's.w[' in body:
                bad.append('%s: plain parameters, but the body reads s.w[]:\n%s' % (name, c))
            if 'SKIPPED' in c or not head:
                bad.append('%s: not written:\n%s' % (name, c))
        if 'Stk' not in parts.get('retfn', '').split('\n', 1)[0]:
            bad.append('ret: expected a Stk parameter:\n%s' % parts.get('retfn'))
        if 'int a10' not in parts.get('stmtfn', '').split('\n', 1)[0]:
            bad.append('stmt: expected plain parameters a4..a10:\n%s' % parts.get('stmtfn'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] stkparams check failed:\n' + '\n'.join(bad))
    print('[stkparams] ok: the caller\'s stack words have the names the parameter list gives them, return line included')


if __name__ == '__main__':
    main()
