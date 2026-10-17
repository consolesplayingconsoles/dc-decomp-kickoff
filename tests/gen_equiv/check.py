#!/usr/bin/env python3
"""The generator's reader on a tiny synthetic function, no game data. Stdlib only.

    check.py        builds a 12-byte SH-4 function in a temp repo (mov.l @(pc),r3 / mov #1,r2 / mov.l r2,@r3 / rts) and checks
                    that scripts/gen_equiv writes the store `*(unsigned int *)0xC2A0000 = 0x1;` for it, and skips a function with a loop
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))


def main():
    tmp = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(tmp, "tools"))
        shutil.copy(os.path.join(SKILL, "scripts", "shdis.py"), os.path.join(tmp, "tools"))
        shutil.copytree(os.path.join(SKILL, "scripts", "gen_equiv"), os.path.join(tmp, "tools", "gen_equiv"))
        code = struct.pack(">6H", 0xD302, 0xE201, 0x2322, 0x000B, 0x0009, 0x0009)          # the function, 12 bytes
        code = struct.pack("<6H", *struct.unpack(">6H", code))                              # the SH-4 is little-endian
        loop = struct.pack("<4H", 0xE400, 0x7401, 0x8BFD, 0x000B)                           # mov #0,r4 / add #1,r4 / bf back / rts
        data = code + struct.pack("<I", 0x0C2A0000) + loop + struct.pack("<H", 0x0009)
        open(os.path.join(tmp, "1ST_READ.BIN"), "wb").write(data)
        open(os.path.join(tmp, "BASE"), "w").write("0C010000\n")
        open(os.path.join(tmp, "functions.txt"), "w").write("F 0c010000 16 storefn\nF 0c010010 10 loopfn\n")
        script = ("import sys; sys.path.insert(0, 'tools/gen_equiv'); import gen_core\n"
                  "c = gen_core.run('storefn')\n"
                  "print(' '.join(c.stmts))\n"
                  "try:\n    gen_core.run('loopfn'); print('LOOP-NOT-SKIPPED')\nexcept gen_core.Skip:\n    print('loop skipped')\n")
        out = subprocess.run([sys.executable, "-c", script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True).stdout
        if "*(unsigned int *)0xC2A0000 = 0x1;" in out and "loop skipped" in out:
            print("[gen_equiv] ok: the store is written, the loop is skipped")
            return
        sys.exit("[ERROR] gen_equiv check failed:\n" + out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
