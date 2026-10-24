#!/usr/bin/env python3
"""The build from C looks for numbers in the C that point into the game code (scripts/tools/8-build/cbuild.py in_code_numbers, and the
rewrite that replaces them). Comment lines are skipped, but a statement that starts with `*` is code: `*(int *)0x0C020040 = 1;` is a
store, and the old test (any line starting with `*`) skipped it, so its address was never found and never rewritten. No game data, no
compiler. Stdlib only.

    check.py      a temp repo with layout.txt, two functions and one C file:
                    code      a line starting with `*(` that stores to an address inside the game code is found
                    comment   `/* ... */` lines, ` * ` continuation lines and ` */` lines are not looked at
                    entry     a function's own address is not reported (it becomes its name)
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
"""


def main():
    tmp = tempfile.mkdtemp()
    try:
        os.chdir(tmp)
        open('layout.txt', 'w').write('game 0C020000 0C030000\n')
        open('functions.txt', 'w').write('F 0c020000 64 f\nF 0c020100 16 g\n')
        open('BASE', 'w').write('0C020000\n')
        open('1ST_READ.BIN', 'wb').write(b'\x09\x00' * 0x200)
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
        if not bad:
            print("[cbuild] ok: a statement starting with `*(` is code, comment lines of every kind are skipped, an entry address is not reported")
            return
        sys.exit("[ERROR] cbuild check failed:\n" + "\n".join(bad))
    finally:
        os.chdir('/')
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
