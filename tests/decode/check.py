#!/usr/bin/env python3
"""The decoder and the classification on tiny synthetic functions, no game data. Stdlib only.

    check.py      builds small SH-4 functions in a temp repo with the tools tree, and checks:
                    jumptable   data after an unconditional branch (a jump table, constants) that decodes as a banked-register
                                instruction is not 'no C form': only code control flow reaches is read (Crazy Taxi: 58 functions
                                were wrongly set aside, putPlayerCar among them)
                    banked      the same instruction reached by the code is 'no C form'
                    poolclaim   a pc-relative load whose pool address lands on an instruction the code runs does not turn that
                                instruction into data (Crazy Taxi: about 30 functions had code shown as .word)
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
RTS, NOP = 0x000B, 0x0009
STC_R0BANK = 0x0082            # stc r0_bank,r0: a banked register, no C form


def bra(d): return 0xA000 | (d & 0xFFF)
def mov_i(n, i): return 0xE000 | (n << 8) | (i & 0xFF)
def movl_pc(n, disp): return 0xD000 | (n << 8) | disp


FUNCS = [
    # bra over two words of data (8 bytes: the branch lands at +8), then return
    ('jumptablefn', [bra(2), NOP, STC_R0BANK, 0x016C, RTS, NOP]),
    ('bankedfn', [STC_R0BANK, RTS, NOP, NOP]),
    # mov.l @(0,pc),r1 at +0 reads the word at +4, which is also the code's own next instruction (mov #1,r2)
    ('poolclaimfn', [movl_pc(1, 0), NOP, mov_i(2, 1), RTS, NOP, NOP]),
]


def main():
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, "scripts", "tools"), os.path.join(tmp, "tools"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        data, lines, where = b'', [], {}
        for name, words in FUNCS:
            where[name] = BASE + len(data)
            code = b''.join(struct.pack('<H', w) for w in words)
            lines.append("F %08x %d %s" % (BASE + len(data), len(code), name))
            data += code
        open(os.path.join(tmp, "1ST_READ.BIN"), "wb").write(data)
        open(os.path.join(tmp, "BASE"), "w").write("%08X\n" % BASE)
        open(os.path.join(tmp, "functions.txt"), "w").write("\n".join(lines) + "\n")
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, classify\n"
                  "exe = open('1ST_READ.BIN', 'rb').read()\n"
                  "for l in open('functions.txt'):\n"
                  "    p = l.split(); print(p[3], classify.no_c_form(exe, %d, int(p[1], 16), int(p[2])))\n" % BASE)
        out = subprocess.run([sys.executable, "-c", script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True).stdout
        verdict = dict(l.split(' ', 1) for l in out.strip().split('\n') if ' ' in l)
        dis = subprocess.run([sys.executable, "tools/shdis.py", "--func", "poolclaimfn"], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True).stdout
        bad = []
        if verdict.get('jumptablefn', '?').strip() != '[]':
            bad.append("jumptable: data after a branch read as code: %s" % verdict.get('jumptablefn'))
        if 'r0_bank' not in verdict.get('bankedfn', ''):
            bad.append("banked: a reached banked-register instruction not reported: %s" % verdict.get('bankedfn'))
        line4 = [l for l in dis.split('\n') if l.startswith('%08x' % (where['poolclaimfn'] + 4))]
        if not line4 or '.word' in line4[0] or 'mov' not in line4[0]:
            bad.append("poolclaim: the instruction at +4 is shown as %s" % (line4[0] if line4 else 'nothing'))
        if not bad:
            print("[decode] ok: data after a branch is not read as code; a reached banked-register instruction is 'no C form'; "
                  "a pool claim on code the function runs leaves it code")
            return
        sys.exit("[ERROR] decode check failed:\n" + "\n".join(bad) + "\n--- classify ---\n" + out + "--- shdis ---\n" + dis)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
