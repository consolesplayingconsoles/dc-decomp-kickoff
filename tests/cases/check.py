#!/usr/bin/env python3
"""Drawing test cases (gen_equiv --draw) on tiny synthetic functions, no game data, no compiler. Stdlib only.

    check.py      builds small SH-4 functions in a temp repo with the tools tree, writes C for them and draws cases:
                    framearg  five calls that pass pointers into the caller's own stack frame, laid out like PutColliWall's (nlSingleLineUseViewMatrix(r15 + 12,
                              r15, colour) in Crazy Taxi's PutColliWall): a stubbed call may answer by writing through its pointer
                              arguments, and writing over the caller's frame (its saved return address) makes the original return
                              into a case's pointer. The drawer must still find cases on which the original finishes.
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
STS_PR, LDS_PR = 0x4F22, 0x4F26


def mov(m, n): return 0x6003 | (n << 8) | (m << 4)
def add_i(n, i): return 0x7000 | (n << 8) | (i & 0xFF)
def jsr(n): return 0x400B | (n << 8)


def code(words, pool=()):
    """Words, padded to 4, then the literal pool; a load is 0xD000 | reg << 8 | index into the pool (filled in here)."""
    out = [w for w in words]
    n = len(out) * 2
    pad = (4 - n % 4) % 4
    data = b''.join(struct.pack('<H', w) for w in out) + b'\x09\x00' * (pad // 2)
    return data + b''.join(struct.pack('<I', v) for v in pool)


def main():
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(os.path.join(SKILL, "scripts", "tools"), os.path.join(tmp, "tools"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        callee = code([0x2462, RTS, 0x2562])          # linefn: mov.l r6,@r4 / rts / mov.l r6,@r5 (reads r4, r5 and r6: three arguments)
        callee_at = BASE
        # the drawer answers calls by writing 4 words through each argument register (a frame array in the C), only when a function
        # makes more than four calls (five here); the checker writes only through the callee's own arguments, so linefn reads three
        # PutColliWall's frame: r14-r11 and fr15-fr12 saved, then pr, then 24 bytes, so the saved pr is at r15 + 24; the calls pass
        # r15 + 12 and r15 (and a constant in r6)
        PUSH = [0x2FE6, 0x2FD6, 0x2FC6, 0x2FB6, 0xFFFB, 0xFFEB, 0xFFDB, 0xFFCB]
        POP = [0xFCF9, 0xFDF9, 0xFEF9, 0xFFF9, 0x6BF6, 0x6CF6, 0x6DF6, 0x6EF6]
        words = PUSH + [STS_PR, add_i(15, -24), None] + [mov(15, 4), mov(15, 5), 0xE6FF, jsr(1), add_i(4, 12)] * 5 + \
            [add_i(15, 24), LDS_PR] + POP[:-1] + [RTS, POP[-1]]
        fn_at = BASE + len(callee)
        nwords = len(words)
        pool_off = (nwords * 2 + 3) & ~3
        pc_at_load = fn_at + 2 * (len(PUSH) + 2)
        words[len(PUSH) + 2] = 0xD100 | ((fn_at + pool_off - ((pc_at_load + 4) & ~3)) // 4)       # mov.l @(disp,pc),r1
        caller = code(words, [callee_at])
        open(os.path.join(tmp, "1ST_READ.BIN"), "wb").write(callee + caller)
        open(os.path.join(tmp, "BASE"), "w").write("%08X\n" % BASE)
        open(os.path.join(tmp, "functions.txt"), "w").write("F %08x %d linefn\nF %08x %d framefn\n" % (callee_at, len(callee), fn_at, len(caller)))
        os.makedirs(os.path.join(tmp, "src"))
        open(os.path.join(tmp, "src", "framefn.c"), "w").write(
            "int linefn(int, int, int);\n\nvoid framefn(void)\n{\n    int stk[6];\n\n" + "    linefn(((int)stk + 12), ((int)stk), -1);\n" * 5 + "}\n")
        out = subprocess.run([sys.executable, "tools/5-generated/gen_equiv", "--draw", "src/framefn.c", "framefn", "--force"],
                             cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout
        line = [l for l in out.split('\n') if l.startswith('framefn')]
        if line and 'cases' in line[0] and 'skipped' not in line[0]:
            print("[cases] ok: a call with pointers into the caller's own frame still gets cases on which the original finishes (%s)"
                  % line[0].split(None, 1)[1].strip())
            return
        sys.exit("[ERROR] cases check failed: framearg: %s\n--- output ---\n%s" % (line[0] if line else 'no line for framefn', out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
