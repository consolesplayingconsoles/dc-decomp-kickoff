#!/usr/bin/env python3
"""A compiler runtime helper the disassembly left unnamed. The generator knows `_divls`, `_quick_mvn` and the rest by name, and takes their operands from
r1, r0 and r2. Listed under FUN_<address> with its real name only in symbols.txt (Zombie Revenge FUN_0c0e5dc0, FUN_0c0e6118) it was read as a function with
no arguments: 137 functions called the division with none of its operands. No game data, no compiler. Stdlib only.

    check.py      div    a call to a FUN_ helper that symbols.txt names `_divls` is r1 / r0 in the C, and the C has no call to it
                  mod    the same for `_modls`
                  copy   a block copy through a FUN_ helper that symbols.txt names `_quick_mvn` is a struct assignment, and the C has no call to it
                  plain  a FUN_ function symbols.txt does not name stays an ordinary call
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
RTS, NOP, STS_PR, LDS_PR = 0x000B, 0x0009, 0x4F22, 0x4F26
LEAF = [RTS, NOP, NOP, NOP, NOP, NOP, NOP, NOP]              # 16 bytes: a callee the generator only needs the name of


def caller(target, setup, delay):
    """sts.l pr / setup / mov.l target,r3 / jsr @r3 / delay / lds.l pr / rts / nop / the pool word: `setup` and `delay` put the operands in their registers"""
    words = [STS_PR] + setup
    at = len(words)
    words += [0xD300, 0x430B, delay, LDS_PR, RTS, NOP]
    if len(words) % 2:
        words.append(NOP)
    pc = BASE + 2 * at                                       # patched below with the real address: only the displacement depends on it, mod 4
    return words, at, target, pc


def layout():
    """[(name, bytes)] and the symbols.txt text"""
    out = [('FUN_0c010000', LEAF), ('FUN_0c010010', LEAF), ('FUN_0c010020', LEAF), ('FUN_0c010030', LEAF)]
    data = b''.join(struct.pack('<%dH' % len(w), *w) for _, w in out)
    res = [(n, struct.pack('<%dH' % len(w), *w)) for n, w in out]
    calls = [('divcaller', 0x0C010000, [0x6143], 0x6053),        # mov r4,r1 / delay mov r5,r0: r1 / r0
             ('modcaller', 0x0C010010, [0x6143], 0x6053),
             ('plaincaller', 0x0C010030, [], 0x0009)]
    for name, target, setup, delay in calls:
        words, at, tg, _ = caller(target, setup, delay)
        start = BASE + len(data)
        pool_at = start + 2 * len(words)
        if pool_at % 4:
            words.append(NOP)
            pool_at += 2
        words[at] = 0xD300 | ((pool_at - ((start + 2 * at + 4) & ~3)) // 4)
        code = struct.pack('<%dH' % len(words), *words) + struct.pack('<I', tg)
        res.append((name, code))
        data += code
    # the block copy: r0 = 16 bytes (mov #16,r0 in the delay slot), r1 = a4, r2 = a5
    words, at, tg, _ = caller(0x0C010020, [0x6143, 0x6253], 0xE010)
    start = BASE + len(data)
    pool_at = start + 2 * len(words)
    if pool_at % 4:
        words.append(NOP)
        pool_at += 2
    words[at] = 0xD300 | ((pool_at - ((start + 2 * at + 4) & ~3)) // 4)
    res.append(('copycaller', struct.pack('<%dH' % len(words), *words) + struct.pack('<I', tg)))
    return res


def main():
    tmp = tempfile.mkdtemp()
    bad = []
    try:
        shutil.copytree(os.path.join(SKILL, 'scripts', 'tools'), os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        data, lines = b'', []
        for name, code in layout():
            lines.append('F %08x %d %s' % (BASE + len(data), len(code), name))
            data += code
        open(os.path.join(tmp, '1ST_READ.BIN'), 'wb').write(data)
        open(os.path.join(tmp, 'BASE'), 'w').write('%08X\n' % BASE)
        open(os.path.join(tmp, 'functions.txt'), 'w').write('\n'.join(lines) + '\n')
        open(os.path.join(tmp, 'symbols.txt'), 'w').write('# the real names of the helpers\n0C010000 _divls\n0C010010 _modls\n0C010020 _quick_mvn\n')
        os.makedirs(os.path.join(tmp, 'src'))
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, gen_core, gen_drv, gen_pipe\n"
                  "for n in sys.argv[1:]:\n"
                  "    try:\n"
                  "        print('@@@@ ' + n); print(gen_drv.build(n, gen_pipe.variants(n, False)[0], False)[0])\n"
                  "    except gen_core.Skip as e:\n"
                  "        print('SKIPPED ' + str(e))\n")
        out = subprocess.run([sys.executable, '-c', script, 'divcaller', 'modcaller', 'copycaller', 'plaincaller'], cwd=tmp, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, universal_newlines=True, env=dict(os.environ, GEN_FRAME='0')).stdout
        parts = {c.split('\n', 1)[0]: c.split('\n', 1)[1] if '\n' in c else '' for c in out.split('@@@@ ')[1:]}
        def body(n):
            return parts.get(n, 'MISSING\n' + out[-400:])
        if ' / ' not in body('divcaller') or 'FUN_0c010000(' in body('divcaller'):
            bad.append('div: want r1 / r0 and no call, got:\n' + body('divcaller'))
        if ' % ' not in body('modcaller') or 'FUN_0c010010(' in body('modcaller'):
            bad.append('mod: want r1 % r0 and no call, got:\n' + body('modcaller'))
        if 'struct' not in body('copycaller') or 'FUN_0c010020(' in body('copycaller'):
            bad.append('copy: want a struct assignment and no call, got:\n' + body('copycaller'))
        if 'FUN_0c010030(' not in body('plaincaller'):
            bad.append('plain: want an ordinary call, got:\n' + body('plaincaller'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit('[ERROR] helperalias check failed:\n' + '\n'.join(bad))
    print('[helperalias] ok: a FUN_ helper symbols.txt names is read as that helper: division, remainder and block copy take their operands; another FUN_ stays a call')


if __name__ == '__main__':
    main()
