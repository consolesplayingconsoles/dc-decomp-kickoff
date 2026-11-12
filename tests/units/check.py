#!/usr/bin/env python3
"""units.py reads the `/* @unit ... */` header of every C file in src/ and puts the unit's object in place of the asm files it replaces
(scripts/tools/1-2-baseline/units.py). Every build of every game goes through it, so the old header forms must read exactly as they
always did, and the added forms (@ddata/@bdata pieces, a unit in a folder of src/) must not change them. Temporary repo, no game data,
no compiler. Stdlib only.

    check.py      a made-up src/ and objects.txt:
                    plain     `@unit A-B` and `@unit A-B -align16`: name, range, no data, the options as written
                    data      `@unit A-B @data C-D -macsave=1 -extra=a=400`: the data range, options in order
                    pieces    `@ddata` / `@bdata` ranges come out as @ddata=a-b / @bdata=a-b tokens before the other options
                    folder    src/player/sonic.c is the unit player/sonic; its object is c_player_sonic.obj
                    nounit    a C file with no @unit line is not a unit (equivalent C that stays out of the build)
                    order     the link order: the asm files a unit covers give way to its object at the first one's place, the rest stay
                    pieceobj  the unit's data, D and B pieces are linked in place of the asm files in their ranges
                    refuse    a range that does not start and end on an asm file, and two units that overlap, stop the build
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
UNITS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '1-2-baseline', 'units.py')

FILES = ['8c010000_a.obj', '8c010010_b.obj', '8c010020_c.obj', '8c010030_d.obj', '8c010040_e.obj', '8c010050_f.obj',
         '8c020000_t.obj', '8c020010_u.obj', '8c020020_v.obj', '8c020030_w.obj']


def repo(units):
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, 'src', 'player'))
    for path, text in units.items():
        open(os.path.join(d, 'src', path), 'w').write(text)
    open(os.path.join(d, 'objects.txt'), 'w').write('\n'.join(FILES) + '\n')
    return d


def run(d, *args):
    r = subprocess.run([sys.executable, '-I', UNITS] + list(args), cwd=d, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def main():
    bad = []

    d = repo({'palette.c': '/* @unit 8C010010-8C010030 -align16 */\nint x;\n',
              'psg.c': '/* @unit 8C010040-8C010050 @data 8C020000-8C020010 -macsave=1 -extra=a=400 */\n',
              'pieces.c': '/* @unit 8C010000-8C010010 @data 8C020010-8C020020 @ddata 8C020020-8C020030 @bdata 8C020030-8C020040 -speed */\n',
              'equiv.c': 'int y;\n',
              'player/sonic.c': '/* @unit 8C010050-8C010060 */\n'})
    # the last range ends past the last file (8C010060, 8C020040): objects.txt must list a file there for the build to accept it
    open(os.path.join(d, 'objects.txt'), 'w').write('\n'.join(FILES + ['8c010060_g.obj', '8c020040_x.obj']) + '\n')
    rc, out, err = run(d, '--units')
    rows = {l.split()[0]: l.split()[1:] for l in out.splitlines()}
    want = {'palette': ['8C010010', '8C010030', '-', '-', '-align16'],
            'psg': ['8C010040', '8C010050', '8C020000', '8C020010', '-macsave=1', '-extra=a=400'],
            'pieces': ['8C010000', '8C010010', '8C020010', '8C020020', '@ddata=8C020020-8C020030', '@bdata=8C020030-8C020040', '-speed'],
            'player/sonic': ['8C010050', '8C010060', '-', '-']}
    for k, v in want.items():
        if rows.get(k) != v:
            bad.append('%s: --units gave %s, expected %s' % (k, rows.get(k), v))
    if 'equiv' in rows:
        bad.append('nounit: a file without an @unit line was read as a unit')

    # the link order of a plain unit and a folder unit (no data pieces: only these two)
    d = repo({'palette.c': '/* @unit 8C010010-8C010030 -align16 */\n', 'player/sonic.c': '/* @unit 8C010050-8C010060 */\n'})
    open(os.path.join(d, 'objects.txt'), 'w').write('\n'.join(FILES[:6] + ['8c010060_g.obj']) + '\n')
    rc, out, err = run(d, 'objects.txt')
    got = out.split()
    want = ['build\\obj\\8c010000_a.obj', 'build\\obj\\c_palette.obj', 'build\\obj\\8c010030_d.obj', 'build\\obj\\8c010040_e.obj',
            'build\\obj\\c_player_sonic.obj', 'build\\obj\\8c010060_g']
    want[-1] += '.obj'
    if rc or got != want:
        bad.append('order: link order %s, expected %s %s' % (got, want, err.strip()))

    # data, D and B pieces take the place of the asm files in their ranges
    d = repo({'pieces.c': '/* @unit 8C010000-8C010010 @data 8C020010-8C020020 @ddata 8C020020-8C020030 @bdata 8C020030-8C020040 */\n'})
    open(os.path.join(d, 'objects.txt'), 'w').write('\n'.join(FILES + ['8c010060_g.obj', '8c020040_x.obj']) + '\n')
    rc, out, err = run(d, 'objects.txt')
    for obj in ('c_pieces.obj', 'c_pieces_data.obj', 'c_pieces_ddata.obj', 'c_pieces_bdata.obj'):
        if 'build\\obj\\' + obj not in out.split():
            bad.append('pieceobj: %s is not in the link order: %s %s' % (obj, out.split(), err.strip()))
    if '8c020010_u' in out or '8c020020_v' in out or '8c020030_w' in out:
        bad.append('pieceobj: an asm file inside a piece range stayed in the link order')

    # refusals
    d = repo({'off.c': '/* @unit 8C010005-8C010030 */\n'})
    rc, out, err = run(d, 'objects.txt')
    if rc == 0 or 'asm file boundaries' not in err:
        bad.append('refuse: a range off the asm file boundaries was accepted')
    d = repo({'one.c': '/* @unit 8C010000-8C010030 */\n', 'two.c': '/* @unit 8C010020-8C010040 */\n'})
    rc, out, err = run(d, 'objects.txt')
    if rc == 0 or 'overlap' not in err:
        bad.append('refuse: two units that overlap were accepted')

    if bad:
        sys.exit('[ERROR] units check failed:\n' + '\n'.join(bad))
    print('[units] ok: the plain, @data, @ddata/@bdata and folder headers read as documented, the link order and the refusals hold')


if __name__ == '__main__':
    main()
