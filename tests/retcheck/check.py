#!/usr/bin/env python3
"""A function's C must return in the register the original returns in (scripts/tools/8-build/retcheck.py). The generator declares the
type from what it reads and equiv.py compares only the declared register, so a function that ends `ftrc; sts fpul,r0` but is declared
float passes every case and hands its callers a leftover (Crazy Taxi: fcvHermiteAngle, the cab driver's arms; CheckColliPoleEdge).
No game data, no compiler: a synthetic executable of four 16-byte functions. Stdlib only.

    check.py      a temp repo with functions.txt, BASE, 1ST_READ.BIN and two C files:
                    int      `ftrc fr1,fpul; rts; sts fpul,r0` returns in r0: declared float, it is reported with r0
                    imm      `mov #1,r0; rts` returns in r0: declared int, it is not reported
                    float    `fldi1 fr1; fmov fr1,fr0; rts` returns in fr0: declared float, it is not reported
                    callee   `jsr @r3; mov #12,r0; rts`: the result is the callee's, nothing is said whatever the declaration
                    pointer  `float *` is a pointer, in r0: `mov.l @(pc),r0; rts` declared `float *` is not reported
                    index    r0 written and then used as an index (`fmov.s fr5,@(r0,r4)`) before the rts is consumed, not returned:
                             declared float, it is not reported
                    callers  a file that declares the float function as int and uses the value is listed by --callers, not an error
                    fixed    with the int function declared int, exit 0
                    cache    build/retcheck.json keeps the original's register per function: the second run reads nothing of it, a wrong declaration
                             is still caught, a corrupt file or a changed functions.txt is read again, and so is an executable of the same
                             size with other bytes (the key held its size only)
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '8-build', 'retcheck.py')

NOP, RTS = 0x0009, 0x000B
FUNCS = {
    # name: (offset, words)
    'f_int': (0x00, [0xF13D, RTS, 0x005A]),            # ftrc fr1,fpul ; rts ; sts fpul,r0
    'f_imm': (0x10, [0xE001, RTS, NOP]),               # mov #1,r0 ; rts ; nop
    'f_flt': (0x20, [0xF19D, 0xF01C, RTS, NOP]),       # fldi1 fr1 ; fmov fr1,fr0 ; rts ; nop
    'f_call': (0x30, [0x430B, 0xE00C, RTS, NOP]),      # jsr @r3 ; mov #12,r0 ; rts ; nop
    'f_ptr': (0x40, [0xD000, RTS, NOP]),                # mov.l @(0,pc),r0 ; rts ; nop  (a pointer result, in r0)
    'f_idx': (0x50, [0x9000, 0xF457, RTS, NOP]),        # mov.w @(0,pc),r0 ; fmov.s fr5,@(r0,r4) ; rts ; nop  (r0 is an index)
}
BASE = 0x0C020000

A = """float f_int(void)
{
    return 1.0f;
}

int f_imm(void)
{
    return 1;
}

float f_flt(void)
{
    return 1.0f;
}

float f_call(void)
{
    return 1.0f;
}

float *f_ptr(void)
{
    return (float *)0x0C100000;
}

float f_idx(int a)
{
    return 2.0f;
}
"""
CALLER = """int f_flt(void);
int f_imm(void);

void g(void)
{
    int x;
    x = f_flt();
    f_imm();
}
"""


def run(*args):
    r = subprocess.run([sys.executable, TOOL] + list(args), capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main():
    tmp = tempfile.mkdtemp()
    try:
        os.chdir(tmp)
        code = bytearray(struct.pack('<H', NOP) * 0x60)
        for off, words in FUNCS.values():
            for k, w in enumerate(words):
                code[off + 2 * k:off + 2 * k + 2] = struct.pack('<H', w)
        open('1ST_READ.BIN', 'wb').write(bytes(code))
        open('BASE', 'w').write('%08X\n' % BASE)
        open('functions.txt', 'w').write(''.join('F %08x 16 %s\n' % (BASE + off, n) for n, (off, _) in sorted(FUNCS.items(), key=lambda kv: kv[1][0])))
        os.makedirs('src')
        open('src/a.c', 'w').write(A)
        open('src/b.c', 'w').write(CALLER)
        bad = []
        rc, out = run()
        first = out
        if rc == 0:
            bad.append('int: a float-declared function that ends `sts fpul,r0` was accepted')
        if 'f_int: declared float' not in out or 'returns in r0' not in out:
            bad.append('int: f_int is not reported with r0: %s' % out.strip())
        for n in ('f_imm', 'f_flt', 'f_call', 'f_ptr', 'f_idx'):
            if ('%s:' % n) in out:
                bad.append('%s: reported although its declaration is right or its result is a callee\'s: %s' % (n, out.strip()))
        rc, out = run('--callers')
        if 'b.c declares f_flt as int' not in out:
            bad.append('callers: b.c declares f_flt as int and uses the value, not listed: %s' % out.strip())
        if 'declares f_imm' in out:
            bad.append('callers: b.c declares f_imm with the right type (and discards the value), yet listed')
        open('src/a.c', 'w').write(A.replace('float f_int(void)\n{\n    return 1.0f;', 'int f_int(void)\n{\n    return 1;'))
        rc, out = run()
        if rc != 0:
            bad.append('fixed: with f_int declared int the check still fails: %s' % out.strip())
        # the cache: the original's registers are read once; the C is still checked every run
        if '(6 function(s) of the original read, 0 from' not in first:
            bad.append('cache: the first run did not read the six functions of the original: %s' % first.strip())
        rc, out = run()
        if rc != 0 or '(0 function(s) of the original read, 6 from build/retcheck.json)' not in out:
            bad.append('cache: the second run read the original again: %s' % out.strip())
        open('src/a.c', 'w').write(A)                       # the wrong declaration comes back: still caught, from the cache
        rc, out = run()
        if rc == 0 or 'f_int: declared float' not in out or '(0 function(s) of the original read' not in out:
            bad.append('cache: a wrong declaration is not caught with the original read from the cache: %s' % out.strip())
        open('src/a.c', 'w').write(A.replace('float f_int(void)\n{\n    return 1.0f;', 'int f_int(void)\n{\n    return 1;'))
        open('build/retcheck.json', 'w').write('not json')
        rc, out = run()
        if rc != 0 or '(6 function(s) of the original read, 0 from' not in out:
            bad.append('cache: an unreadable cache was not read again from the original: %s' % out.strip())
        open('functions.txt', 'a').write('F %08x 16 f_extra\n' % (BASE + 0x70))
        rc, out = run()
        if '(0 function(s) of the original read, 6 from' in out:
            bad.append('cache: a changed functions.txt kept the old cache: %s' % out.strip())
        rc, out = run()                                     # settled on the new functions.txt
        exe = bytearray(open('1ST_READ.BIN', 'rb').read())
        exe[-1] ^= 0xFF
        open('1ST_READ.BIN', 'wb').write(bytes(exe))       # same size, other bytes
        rc, out = run()
        if '(0 function(s) of the original read' in out:
            bad.append('cache: an executable of the same size with other bytes kept the old cache: %s' % out.strip())
        if not bad:
            print('[retcheck] ok: an int in r0 declared float is refused; right declarations and callee results pass; callers listed on request')
            return
        sys.exit('[ERROR] retcheck check failed:\n' + '\n'.join(bad))
    finally:
        os.chdir('/')
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
