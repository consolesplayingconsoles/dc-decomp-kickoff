#!/usr/bin/env python3
"""The addresses a function touches that follow from its arguments (scripts/tools/5-generated/gen_equiv/gen_drv.py addr_vals), on
expressions the reader writes. No game data, no compiler. Stdlib only.

Drawing evaluates a memory address as Python after putting the argument values in. A table index made from a comparison, which C writes
as `(a4 > 0x100) ? 1 : 0`, stopped it ("Skip addr expr", Virtua Tennis cpuDblSignalPut: 0x8C3343AC + (((int)a4 > (int)0x100 ? 1 : 0) << 2)).

    check.py      ternary   that address with a4 = 0x0C800000 (a pointer, above 0x100) is 0x8C3343B0, with a4 = 5 it is 0x8C3343AC
                  plain     an address with no ternary still evaluates as before
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
tmp = tempfile.mkdtemp()
os.chdir(tmp)
open('functions.txt', 'w').write('F 8c020000 64 fn\n')
open('BASE', 'w').write('8C020000\n')
open('1ST_READ.BIN', 'wb').write(b'\x00\x09' * 32)
sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401
import gen_drv  # noqa: E402


class C:
    def __init__(self, exprs):
        self.mem_addrs = [('e', e) for e in exprs]


def main():
    bad = []
    tern = '(0x8C3343AC + (((((int)a4 > (int)0x100)) ? 1 : 0) << 2))'
    plain = '(0x8C100000 + (a4 << 2))'
    for name, exprs, base, want in (('ternary high', [tern], {'a4': 0x0C800000}, [0x8C3343B0]),
                                    ('ternary low', [tern], {'a4': 5}, [0x8C3343AC]),
                                    ('plain', [plain], {'a4': 3}, [0x8C10000C])):
        try:
            got = gen_drv.addr_vals(C(exprs), base)
        except Exception as e:
            got = '%s %s' % (type(e).__name__, str(e)[:60])
        if got != want:
            bad.append('%s: %s, want %s' % (name, got if isinstance(got, str) else [hex(x) for x in got], [hex(x) for x in want]))
    if bad:
        sys.exit('[ERROR] addrexpr check failed:\n' + '\n'.join(bad))
    print('[addrexpr] ok: an address with a C conditional in it evaluates')


if __name__ == '__main__':
    main()
