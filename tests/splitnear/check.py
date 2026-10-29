#!/usr/bin/env python3
"""A kept asm piece calls with bsr/bra (4 KB reach), so it must lie next to the C function it calls. When that function sits in a file
with other functions, the file can be kilobytes long and no layout brings the piece within reach (Virtua Tennis, the first time its C
fitted: nlObjPutMVAsm calls nl_objput_mv_send_p0, 9 KB into gen_z; 72 short branches in 10 pieces did not reach).
scripts/tools/8-build/cbuild.py split_near moves each such function to a build file of its own. No game data, no compiler. Stdlib only.

    check.py      a temp repo with one generated file (f, g, and a static h that g uses) and a piece that does `BSR _g`:
                    own       build/cbuild/src/nb_g.c holds g and h, the file's declarations, and not f
                    rest      gen_x.c no longer defines g, and still defines f and h
                    map       near.json maps g to nb_g, and game_set() gives nb_g for g, gen_x for f
                    alone     a file whose only game function the piece calls is left as it is
"""
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')

C = """typedef struct { int w[3]; } Stk3;
int f(int a4);
int g(int a4);

static int h(int a)
{
    return a + 1;
}

int f(int a4)
{
    return a4 * 2;
}

int g(int a4)
{
    return h(a4);
}
"""
SOLO = """int k(int a4);

int k(int a4)
{
    return a4;
}
"""
DEF = re.compile(r'^[A-Za-z_][\w \t\*]*?\b(\w+)\s*\([^;{]*\)\s*\n?\{', re.M)


def main():
    tmp = tempfile.mkdtemp()
    try:
        os.chdir(tmp)
        open('layout.txt', 'w').write('game 0C020000 0C030000\n')
        open('BASE', 'w').write('0C020000\n')
        open('1ST_READ.BIN', 'wb').write(b'\x09\x00' * 0x100)
        open('functions.txt', 'w').write('F 0c020000 16 f\nF 0c020010 16 g\nF 0c020020 16 k\nF 0c020100 64 p\n')
        os.makedirs('tests/gen_x')
        os.makedirs('tests/gen_y')
        open('tests/equivalent.txt', 'w').write('f\ng\nk\n')
        for d, n in (('gen_x', 'f'), ('gen_x', 'g'), ('gen_y', 'k')):
            open('tests/%s/%s.json' % (d, n), 'w').write('[]')
        os.makedirs('build/cbuild/src')
        os.makedirs('build/cbuild/asm')
        open('build/cbuild/src/gen_x.c', 'w').write(C)
        open('build/cbuild/src/gen_y.c', 'w').write(SOLO)
        open('build/cbuild/asm/0c020100_p.src', 'w').write('_p:\n    BSR _g\n    NOP\n    BSR _k\n    NOP\n    RTS\n    NOP\n')
        sys.path.insert(0, os.path.join(TOOLS, '8-build'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import cbuild
        bad = []
        if not hasattr(cbuild, 'split_near'):
            sys.exit('[ERROR] splitnear check failed:\ncbuild has no split_near()')
        cbuild.split_near()
        defs = lambda p: [m.group(1) for m in DEF.finditer(open(p).read())] if os.path.exists(p) else None
        own = defs('build/cbuild/src/nb_g.c')
        if own is None or sorted(own) != ['g', 'h']:
            bad.append('own: nb_g.c defines %s, not g and h' % own)
        elif 'typedef struct' not in open('build/cbuild/src/nb_g.c').read():
            bad.append('own: nb_g.c lost the file\'s declarations')
        rest = defs('build/cbuild/src/gen_x.c')
        if sorted(rest or []) != ['f', 'h']:
            bad.append('rest: gen_x.c defines %s, not f and h' % rest)
        near = json.load(open('build/cbuild/near.json')) if os.path.exists('build/cbuild/near.json') else None
        if near != {'g': 'nb_g'}:
            bad.append('map: near.json is %s' % near)
        gs = cbuild.game_set()
        if gs.get('g') != 'nb_g' or gs.get('f') != 'gen_x':
            bad.append('map: game_set() gives g: %s, f: %s' % (gs.get('g'), gs.get('f')))
        if os.path.exists('build/cbuild/src/nb_k.c') or open('build/cbuild/src/gen_y.c').read() != SOLO:
            bad.append('alone: gen_y.c, whose only function the piece calls, was split')
        if not bad:
            print('[splitnear] ok: a function a piece reaches by bsr goes to a file of its own with its statics, the rest stays, '
                  'game_set() follows it, a file holding only that function is left alone')
            return
        sys.exit('[ERROR] splitnear check failed:\n' + '\n'.join(bad))
    finally:
        os.chdir('/')
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
