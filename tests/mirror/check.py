#!/usr/bin/env python3
"""A game linked at 8C010000 (the cached mirror: Virtua Tennis) lists its functions in functions.txt as 8c..., while layout.txt and the
build tools work in the 0C mirror of the same RAM (Crazy Taxi and Zombie Revenge are 0C all through). The build read functions.txt as
written, so no 8c function fell inside the 0C game region: "0 files; 0 game functions kept", an empty link, and the error "the game
block does not fit the original space" for a game that had not been compiled at all (Virtua Tennis, 2026-10-29). Every build tool reads
the functions through layout.functions(), which maps an address to the 0C mirror. No game data, no compiler. Stdlib only.

    check.py      a temp repo with layout.txt `game 0C020000 0C030000` and functions.txt in 8c form:
                    layout    layout.functions() gives the 0C addresses
                    cbuild    game_set() finds the function in the game region
                    relocasm  functions() gives the 0C addresses
                    zero      0c-form functions.txt (CT, ZR) gives the same
                    boundaries  BASE, entries() and word() work in the 0C mirror, and word() takes either mirror of an address
                    objects   cbuild reads objects.txt (8c names) in the 0C mirror: a file inside the game block is not past it,
                              a file past it is, and boot_split() finds the file that runs into the block (the link took every old
                              file of Virtua Tennis again beside the C: 3,310 duplicate symbols, the first time its C fitted)
                    parts     with no fill block in layout.txt the fit asks only for PB2 (Virtua Tennis has none: asking for PB1
                              failed a link that fitted), and with one it asks for both
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')


def main():
    tmp = tempfile.mkdtemp()
    try:
        os.chdir(tmp)
        open('layout.txt', 'w').write('game 0C020000 0C030000\n')
        open('BASE', 'w').write('8C020000\n')
        open('1ST_READ.BIN', 'wb').write(b'\x09\x00' * 0x180)
        os.makedirs('tests/gen_x')
        open('tests/equivalent.txt', 'w').write('f\n')
        open('tests/gen_x/f.json', 'w').write('[]')
        sys.path.insert(0, os.path.join(TOOLS, '8-build'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import layout
        bad = []
        want = [(0x0C020000, 64, 'f'), (0x0C020100, 16, 'g')]
        for form, text in (('8c', 'F 8c020000 64 f\nF 8c020100 16 g\n'), ('0c', 'F 0c020000 64 f\nF 0c020100 16 g\n')):
            open('functions.txt', 'w').write(text)
            got = layout.functions() if hasattr(layout, 'functions') else None
            if got != want:
                bad.append('layout (%s): layout.functions() is %s' % (form, got))
            import cbuild
            import relocasm
            gs = cbuild.game_set()
            if gs != {'f': 'gen_x'}:
                bad.append('cbuild (%s): game_set() is %s, not {f: gen_x}' % (form, gs))
            if relocasm.functions() != want:
                bad.append('relocasm (%s): functions() is %s' % (form, relocasm.functions()))
        # boundaries: the executable read at either mirror of an address (BASE 8C020000 in the file)
        open('functions.txt', 'w').write('F 8c020000 64 f\nF 8c020100 16 g\n')
        import boundaries
        for a in (0x0C020002, 0x8C020002):
            try:
                if boundaries.word(a) != 0x0009:
                    bad.append('boundaries: word(%X) is not the nop at offset 2' % a)
            except Exception as e:
                bad.append('boundaries: word(%X) fails: %s' % (a, e))
        if boundaries.entries()[0][0] != 0x0C020000:
            bad.append('boundaries: entries() gives %X, not the 0C mirror' % boundaries.entries()[0][0])
        if boundaries.BASE != 0x0C020000:
            bad.append('boundaries: BASE is %X, not the 0C mirror' % boundaries.BASE)
        # objects: objects.txt in 8c form against the 0C regions (no fill block: the game code starts the block)
        open('objects.txt', 'w').write('8c01ff00_a.src\n8c020100_g.src\n8c030000_t.src\n')
        if not hasattr(cbuild, 'obj_addr'):
            bad.append('objects: cbuild has no obj_addr(), objects.txt is compared as written')
        else:
            if cbuild.obj_addr('8c020100_g.src') >= cbuild.G1:
                bad.append('objects: 8c020100 (inside the game block) is counted past it')
            if cbuild.obj_addr('8c030000_t.src') < cbuild.G1:
                bad.append('objects: 8c030000 (past the game block) is counted inside it')
        if cbuild.boot_split() != (0x0C01FF00, 'a'):
            bad.append('objects: boot_split() is %s, not the file at 0C01FF00 that runs into the block' % (cbuild.boot_split(),))
        # parts: no fill block here; a fill block in a second layout.txt (the module reads it at import)
        if cbuild.part_regions() != {'PB2': (0x0C020000, 0x0C030000)} if hasattr(cbuild, 'part_regions') else True:
            bad.append('parts: with no fill block the fit asks for %s, not PB2 alone' % (getattr(cbuild, 'part_regions', lambda: 'PB1 and PB2')(),))
        open('layout.txt', 'w').write('game 0C020000 0C030000\nfill 0C010000 0C018000\n')
        sys.modules.pop('cbuild')
        import cbuild as cb2
        if not hasattr(cb2, 'part_regions') or cb2.part_regions() != {'PB1': (0x0C010000, 0x0C018000), 'PB2': (0x0C020000, 0x0C030000)}:
            bad.append('parts: with a fill block the fit does not ask for PB1 and PB2')
        if not bad:
            print('[mirror] ok: 8c and 0c functions.txt both give the 0C addresses to layout, cbuild, relocasm and boundaries; '
                  'cbuild reads 8c objects.txt in the 0C mirror')
            return
        sys.exit('[ERROR] mirror check failed:\n' + '\n'.join(bad))
    finally:
        os.chdir('/')
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
