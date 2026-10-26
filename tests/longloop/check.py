#!/usr/bin/env python3
"""Case drawing for a function whose loop runs a fixed, long count (scripts/tools/5-generated/gen_equiv/gen_drv.py tests), with the real
simulator on synthetic code, no game data, no compiler. Stdlib only.

    check.py      a temp repo with one function: a 60,000-round dt loop on a constant from its pool (about 120,000 instructions):
                    longloop  cases are drawn for it. Drawing ran the original for at most max(100000, size*60) instructions, so every case
                              "did not finish" though the check itself allows 2,000,000 (Zombie Revenge adxf_wait_1ms, 100,003
                              instructions; Virtua Tennis ndbClear, 1,966,107)
                    pastcap   a fixed loop past even the check's 2,000,000 instructions (1,200,000 rounds, about 2,400,000; Virtua Tennis
                              crowdSetup finishes at 2,533,314) gets a case that carries its own step limit, and one case is enough for
                              a function with no register inputs
                    loopptr   a copy loop whose pointers are loop variables started from a4 and a5 (Virtua Tennis vmsfs_memcpyl) gets cases:
                              a parameter counted as an address only where it appeared in an address itself, so a4 and a5 were drawn
                              as 1 or FFFFFFFE and every case read unaligned memory
                    halt      a function that never returns by design (bra . / nop: Virtua Tennis SJMEM_Error, SJRBF_Error, SJUNI_Error)
                              gets cases marked endless, which the check passes when both sides run to the step limit
                    gbr       a function that reads and writes through GBR (Virtua Tennis nlSetPaletteData; 92 VT and 361 ZR functions)
                              gets cases with GBR on RAM: the cases left it 0, so @(0,gbr) wrote device memory and every case was thrown
                              out as a wild pointer
                    falloff   a function with no return of its own that runs into the next one (a cut-off shared tail: Virtua Tennis
                              padVibOff, motionSet) is not taken for one that never returns
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
BASE = 0x8C010000
CODE = [0xD402, 0x4410, 0x8BFD, 0x000B, 0x0009, 0x0009]      # mov.l @(pool),r4 / dt r4 / bf .-2 / rts / nop / nop
BIG = [0xD402, 0x4410, 0x8BFD, 0x000B, 0x0009, 0x0009]       # the same dt loop on a pool constant of 1,200,000
HALT = [0xAFFE, 0x0009]                                       # bra . / nop: an error trap
GBRF = [0xC401, 0x7001, 0x000B, 0xC000]                       # mov.b @(1,gbr),r0 / add #1,r0 / rts / mov.b r0,@(0,gbr)
FALL = [0xE001, 0xE102]                                       # mov #1,r0 / mov #2,r1: runs on into the next function
COPY = [0x4609, 0x6156, 0x4610, 0x2412, 0x8FFB, 0x7404, 0x000B, 0x0009]      # shlr2 r6 / mov.l @r5+,r1 / dt r6 / mov.l r1,@r4 / bf/s / add #4,r4 / rts


def main():
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        data = b''.join(struct.pack('<H', w) for w in CODE) + struct.pack('<I', 60000)
        copy = b''.join(struct.pack('<H', w) for w in COPY)
        halt = b''.join(struct.pack('<H', w) for w in HALT)
        fall = b''.join(struct.pack('<H', w) for w in FALL)
        gbrf = b''.join(struct.pack('<H', w) for w in GBRF)
        big = b''.join(struct.pack('<H', w) for w in BIG) + struct.pack('<I', 1200000)
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(fall + data + copy + halt + gbrf + big)
        BASE_ = BASE + len(fall)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d fallfn\nF %08x %d waitfn\nF %08x %d copyfn\nF %08x %d haltfn\nF %08x %d gbrfn\nF %08x %d bigfn\n' % (BASE, len(fall), BASE_, len(data), BASE_ + len(data), len(copy), BASE_ + len(data) + len(copy), len(halt), BASE_ + len(data) + len(copy) + len(halt), len(gbrf), BASE_ + len(data) + len(copy) + len(halt) + len(gbrf), len(big)))
        os.makedirs(os.path.join(tmp, 'src')); os.makedirs(os.path.join(tmp, 'tests')); os.makedirs(os.path.join(tmp, 'build'))
        script = ("import sys; sys.path[:0] = ['tools', 'tools/5-generated/gen_equiv']; import toolpath, gen_core, gen_drv, gen_pipe\n"
                  "print('NR fallfn', gen_drv.never_returns('fallfn'), 'haltfn', gen_drv.never_returns('haltfn'))\n"
                  "for n in sys.argv[1:]:\n"
                  "    v = gen_pipe.variants(n, False); s, c = gen_drv.build(n, v[0], False)\n"
                  "    try:\n"
                  "        t = gen_drv.tests(n, c, s); print(n, 'CASES', len(t['dev']) + len(t['holdout']), 'endless' if all(d.get('endless') for d in t['dev']) else '', 'gbr' if all(d.get('gbr') for d in t['dev']) else '', 'steps=%s' % max(d.get('steps', 0) for d in t['dev']))\n"
                  "    except gen_core.Skip as e:\n"
                  "        print(n, 'SKIP', e)\n")
        env = dict(os.environ, GEN_DRAW_SECONDS='20')
        out = subprocess.run([sys.executable, '-c', script, 'waitfn', 'copyfn', 'haltfn', 'gbrfn', 'bigfn'], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True, env=env).stdout
        bad = []
        if 'waitfn CASES' not in out:
            bad.append('longloop: no cases for a 60,000-round fixed loop: %s' % out.strip()[-300:])
        if 'copyfn CASES' not in out:
            bad.append('loopptr: no cases for a copy loop over pointers started from a4 and a5: %s' % out.strip()[-300:])
        if not any(l.startswith('haltfn CASES') and 'endless' in l.split() for l in out.splitlines()):
            bad.append('halt: no endless cases for a function that never returns (bra .): %s' % out.strip()[-300:])
        if not any(l.startswith('gbrfn CASES') and 'gbr' in l.split() for l in out.splitlines()):
            bad.append('gbr: no cases with GBR set for a function using @(disp,gbr): %s' % [l for l in out.splitlines() if l.startswith('gbrfn')])
        bl = [l for l in out.splitlines() if l.startswith('bigfn')]
        if not bl or 'CASES' not in bl[0] or int(bl[0].split('steps=')[1]) < 2400000:
            bad.append('pastcap: no case carrying a step limit past 2,400,000 for a 1,200,000-round loop: %s' % bl)
        if 'NR fallfn False haltfn True' not in out:
            bad.append('falloff: never_returns should be False for a fall-through, True for bra .: %s' % [l for l in out.splitlines() if l.startswith('NR')])
        if bad:
            sys.exit('[ERROR] longloop check failed:\n' + '\n'.join(bad))
        print('[longloop] ok: cases are drawn for a function whose fixed loop runs past the fast step cap')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
