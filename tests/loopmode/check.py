#!/usr/bin/env python3
"""The size mode (fschg) a loop's exits leave is the one the code after the loop starts with
(scripts/tools/5-generated/gen_equiv/gen_core.py, exec_loop). No game data, no compiler. Stdlib only.

The state after a loop was set from its exits' registers only: the FPU mode stayed whatever the last path read inside the loop had
left. A loop whose exits run into the tail of the function (fschg back, rts) was read with that tail once inside the loop, which left
the mode switched back, and once after it, which switched it again: the function ended in size mode 1 and was refused ("FPU mode not
restored"). Zombie Revenge's vertex transform loops (FUN_0c0e9500 and three like it) are of this shape.

    check.py      a function that does fschg, runs a counted loop with several entries and two exits into one tail (fschg back, rts),
                  its control flow written with a small assembler below and nothing else in it:
                    written   the generator writes it (it skipped: FPU mode not restored)
"""
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


# a tiny assembler for the few instructions the control flow needs; a label is a name and a colon, a branch target is a label
def asm(lines):
    lab={}; ins=[]
    for l in lines:
        l=l.strip()
        if not l: continue
        if l.endswith(':'): lab[l[:-1]]=len(ins); continue
        ins.append(l)
    out=[]
    for i,l in enumerate(ins):
        p=l.split(None,1); mn=p[0]; a=[x.strip() for x in p[1].split(',')] if len(p)>1 else []
        r=lambda x:int(x[1:])
        d=lambda t:lab[t]-i-2
        if mn=='fschg': w=0xF3FD
        elif mn=='nop': w=0x0009
        elif mn=='rts': w=0x000B
        elif mn=='dt': w=0x4010|(r(a[0])<<8)
        elif mn=='movi': w=0xE000|(r(a[1])<<8)|(int(a[0])&0xFF)
        elif mn=='addi': w=0x7000|(r(a[1])<<8)|(int(a[0])&0xFF)
        elif mn=='tsti': w=0xC800|int(a[0])
        elif mn=='mov': w=0x6003|(r(a[1])<<8)|(r(a[0])<<4)
        elif mn=='add': w=0x300C|(r(a[1])<<8)|(r(a[0])<<4)
        elif mn=='ldpost': w=0x6006|(r(a[1])<<8)|(r(a[0])<<4)
        elif mn=='ld': w=0x6002|(r(a[1])<<8)|(r(a[0])<<4)
        elif mn=='bt': w=0x8900|(d(a[0])&0xFF)
        elif mn=='bf': w=0x8B00|(d(a[0])&0xFF)
        elif mn=='bts': w=0x8D00|(d(a[0])&0xFF)
        elif mn=='bfs': w=0x8F00|(d(a[0])&0xFF)
        elif mn=='bra': w=0xA000|(d(a[0])&0xFFF)
        else: raise ValueError('no such mnemonic: ' + l)
        out.append(w)
    return out
SK='''
 ldpost r4,r9
 fschg
 ld r4,r0
 movi 3,r3
 tsti 1
 bf Ltop
 mov r4,r14
Ltop:
 dt r3
 ldpost r4,r0
 bts Lx1
 ldpost r4,r14
 tsti 1
 mov r6,r2
 bts Lb
 add r4,r14
 mov r4,r14
 addi 24,r4
 addi -8,r14
Lb:
 addi 32,r4
 dt r3
 ldpost r4,r0
 bts Lx2
 ldpost r4,r14
 tsti 1
 bts Lc
 add r4,r14
 mov r4,r14
 addi 24,r4
 addi -8,r14
Lc:
 addi 32,r4
 addi 64,r6
 bra Ltop
 addi 64,r5
Lx2:
 dt r9
 movi -1,r2
 bt Lf1
 tsti 1
 movi 3,r3
 bts Lc
 add r4,r14
 mov r4,r14
 addi 24,r4
 bra Lc
 addi -8,r14
 nop
Lf1:
 addi 32,r5
 bra Ltail
 mov r6,r6
Lx1:
 dt r9
 movi -1,r2
 bt Ltail
 tsti 1
 movi 3,r3
 bts Lb
 add r4,r14
 mov r4,r14
 addi 24,r4
 bra Lb
 addi -8,r14
 nop
Ltail:
 addi 32,r5
 fschg
 movi 0,r0
 rts
 addi 32,r6
'''.strip().split('\n')
WORDS = asm(SK)


def main():
    bad = []
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        code = W(WORDS) + (W([0x0009]) if len(WORDS) % 2 else b'')
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(code)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('F %08x %d f\n' % (BASE, len(code)))
        os.makedirs(os.path.join(tmp, 'src'))
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv\n"
                  "try:\n"
                  "    print(gen_drv.build('f', 'r0', False)[0])\n"
                  "except gen_core.Skip as e:\n"
                  "    print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        if 'SKIPPED' in out or 'int f(' not in out:
            bad.append('written: the generator did not write it:\n%s' % out[:400])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] loopmode check failed:\n' + '\n'.join(bad))
    print("[loopmode] ok: the size mode after a loop is the one its exits leave")


if __name__ == '__main__':
    main()
