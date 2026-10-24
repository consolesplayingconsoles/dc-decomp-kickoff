#!/usr/bin/env python3
"""The build from C looks for numbers in the C that point into the game code (scripts/tools/8-build/cbuild.py in_code_numbers, and the
rewrite that replaces them). Comment lines are skipped, but a statement that starts with `*` is code: `*(int *)0x0C020040 = 1;` is a
store, and the old test (any line starting with `*`) skipped it, so its address was never found and never rewritten. No game data, no
compiler. Stdlib only.

    check.py      a temp repo with layout.txt, two functions and one C file:
                    code      a line starting with `*(` that stores to an address inside the game code is found
                    comment   `/* ... */` lines, ` * ` continuation lines and ` */` lines are not looked at
                    entry     a function's own address is not reported (it becomes its name)
                    middle    a C call to an address inside another C function's code (not its entry) stops pieces() with an error that
                              names the address, the function and the offset, and the C line (Crazy Taxi: Exec_LCD was cut at 210
                              bytes over Exec_LCDLogoDemo and its C called Exec_LCDLogoDemo+140; the second copy the build made
                              popped a frame nobody pushed, and the game froze at the memory card window)
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')

C = """void f(void)
{
*(int *)0x0C020040 = 1;
/* comment 0x0C020044 */
 * continuation 0x0C020048
 */
    *(int *)0x0C02004C = 2;
    g(0x0C020100);
}

void h(void)
{
    ((int (*)(void))(0x0C020104))();
}
"""


def main():
    tmp = tempfile.mkdtemp()
    try:
        os.chdir(tmp)
        open('layout.txt', 'w').write('game 0C020000 0C030000\n')
        open('functions.txt', 'w').write('F 0c020000 64 f\nF 0c020100 16 g\nF 0c020200 16 h\n')
        open('BASE', 'w').write('0C020000\n')
        # the code: nops, with f ending in rts at +0x38 so that 0x0C020040 and 0x0C02004C after it are data (tables), not reached code;
        # g (0x0C020100, 16 bytes) is nops then rts, so g+4 is code
        code = bytearray(b'\x09\x00' * 0x180)
        code[0x38:0x3A] = b'\x0b\x00'
        code[0x10C:0x10E] = b'\x0b\x00'                   # g ends in rts too (it has no C: the build re-assembles it as a piece)
        open('1ST_READ.BIN', 'wb').write(bytes(code))
        os.makedirs('src')
        open('src/x.c', 'w').write(C)
        sys.path.insert(0, os.path.join(TOOLS, '8-build'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import cbuild
        found = cbuild.in_code_numbers('src')
        bad = []
        if 0x0C020040 not in found:
            bad.append('code: a statement starting with `*(` is skipped as a comment (found %s)' % sorted('%X' % a for a in found))
        if 0x0C02004C not in found:
            bad.append('code: an indented statement starting with `*(` is not found')
        for a in (0x0C020044, 0x0C020048):
            if a in found:
                bad.append('comment: %X is in a comment and was found' % a)
        if 0x0C020100 in found:
            bad.append('entry: a function\'s own address is reported')
        # middle: pieces() must refuse the call into g+4 (the C is copied where the build reads it; g's code is nops, all reached)
        os.makedirs('build/cbuild/src')
        open('build/cbuild/src/x.c', 'w').write(C)
        os.makedirs('tests')
        open('tests/equivalent.txt', 'w').write('f\ng\nh\n')           # g has C too: a call into the middle of a function kept as asm is fine (its layout stays)
        open('objects.txt', 'w').write('0c020000_f.src\n0c020100_g.src\n0c020200_h.src\n')
        try:
            cbuild.pieces()
            bad.append('middle: a C call into g+4 (0C020104) was accepted')
        except SystemExit as e:
            msg = str(e)
            if 'middle of a function' not in msg or '0C020104' not in msg or 'g+4' not in msg or 'x.c:' not in msg:
                bad.append('middle: the error does not name the address, g+4 and the C line: %s' % msg)
            if '0C020040' in msg or '0C02004C' in msg:
                bad.append('middle: a data address after f\'s rts is reported as code: %s' % msg)
        if not bad:
            print("[cbuild] ok: a statement starting with `*(` is code, comment lines of every kind are skipped, an entry address is not reported, a call into a function's middle is refused")
            return
        sys.exit("[ERROR] cbuild check failed:\n" + "\n".join(bad))
    finally:
        os.chdir('/')
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
