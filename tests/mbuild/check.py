#!/usr/bin/env python3
"""The build from C on the movable split (scripts/tools/8-build/mbuild.py): the C's address numbers as symbols, and where each
symbol lands once the image is linked. No game data, no compiler. Stdlib only.

    check.py      rewrite_literals() and mapper() on made-up pieces:
                    literal   *(int *)0x8C2FC69C in a C line is *(int *)((int)A_8C2FC69C), declared once; 0x12345678 (no address),
                              0x0C600000 (above the range) and an address in a comment line stay
                    piece     an address 8 bytes into a piece is 8 bytes into that piece's label, in the same mirror
                    cfun      a C function's entry is the C function's symbol
                    middle    the middle of a C function is its second copy when there is one, nothing (None) when not
                    bss       an address past the image is _bss + the same offset
                    bss_start the BSS block starts word aligned: an image end on a word is kept, 0C9E293F becomes 0C9E2940
                    flag      layout.txt `mixed 1` switches the behaviours below on; a missing line or `0` is off
                    define    lnk_hex(): a value that starts with a letter (AC210C5A) gets a leading 0, the others are as they were
                    routes    split_routes(): a branch near a unit's start gets its veneer before the unit, only when allowed
                    ties      cond_ties(): a conditional branch into another group joins the two; copy_extent() takes the groups between
                    tramp     tramp_text(): the first 12 bytes of a replaced function's hole (14 from an address 2 mod 4, so the pool
                              word is aligned) become mov.l / jmp @r0 / nop and the pool word with the C function; too short, or a
                              pool word among them, and the hole stays
                    retarget  retarget_branches(): a conditional branch goes into any hole, a call only into a callable one
                    fit_text  fit_text(): the last line says 'N bytes (K KB) over fixed' or 'N bytes spare', not just fits / DOES NOT FIT
                    holes     hole_pieces(): replaced pieces from the first kept piece to the end of the group are holes (a pool donor after the\n                              last kept piece too), none before it or in a group with no kept piece\n                    holepool  hole_text(): a piece the C replaces keeps its words (a pool word stays a symbol), not zeros\n                    bsspad    bss_pad(end, start) puts _bss at the original image end modulo 32; the pad is written before the _bss label
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(SKILL, 'scripts', 'tools', '8-build'))
sys.path.insert(0, os.path.join(SKILL, 'scripts', 'tools'))


def main():
    os.chdir(HERE)                                   # layout.py reads layout.txt from the working directory: none here
    import mbuild as M
    bad = []
    src = ('/* reads 0x8C2FC69C\n   * and 0x8C2FC6A0 on the next line */\n'
           'int f(void) { return *(int *)0x8C2FC69C + *(int *)0x8C2FC69C + 0x12345678 + *(int *)0x0C600000; }\n'
           'void g(void) {\n    *(unsigned int *)0x8C20D120 = 0x0;\n}\n')
    t, used = M.rewrite_literals(src, 0x0C010000, 0x0C500000)
    if used != {0x8C2FC69C, 0x8C20D120}:
        bad.append('literal: values %r, want {8C2FC69C, 8C20D120}: a line starting with `*(` is code, a comment\'s second line is not'
                   % sorted('%08X' % v for v in used))
    if t.count('extern char A_8C2FC69C[];') != 1 or t.count('((int)A_8C2FC69C)') != 2:
        bad.append('literal: not declared once and used twice:\n' + t)
    if '0x12345678' not in t or '0x0C600000' not in t or '/* reads 0x8C2FC69C' not in t or '* and 0x8C2FC6A0' not in t:
        bad.append('literal: a number that is no address in the range, or a comment, was rewritten:\n' + t)
    hdr = '#define putCab ((int (*)(int))0x0C0200E4)\n#if DEMO == 0x0C0200E4\n#endif\n'
    th, uh = M.rewrite_literals(hdr, 0x0C010000, 0x0C500000)
    if uh != {0x0C0200E4} or '(int (*)(int))((int)A_0C0200E4)' not in th or '#if DEMO == 0x0C0200E4' not in th:
        bad.append('header: a function-pointer define is rewritten to its symbol and a #if line is left alone:\n' + th)
    ts, us = M.rewrite_literals('unsigned int tab = c ? 0x0C0E1C78u : 0x0C0DB008UL;\nint z = 0x12345678u;\n', 0x0C010000, 0x0C500000)
    if us != {0x0C0E1C78, 0x0C0DB008} or ts.count('((unsigned int)A_0C0DB008)') != 1 or '0x12345678u' not in ts or '008)UL' in ts:
        bad.append('suffix: 0x0C0DB008u is an address with an unsigned suffix (Snake Way and Tux Racer\'s request table): \n' + ts)
    mac = '#define TAXI ((unsigned char *)0x0C2AD000)\n#define PTR (*(unsigned char **)0x0C2AD1D8)\n#define N 0x0C2AD000\nint f(void) { return *(int *)0x0C2AD000; }\n'
    tm, _ = M.rewrite_literals(mac, 0x0C010000, 0x0C500000, macro_consts=True)
    tn, _ = M.rewrite_literals(mac, 0x0C010000, 0x0C500000)
    if ('((unsigned char *)A_0C2AD000)' not in tm or '(*(unsigned char **)A_0C2AD1D8)' not in tm or '#define N ((int)A_0C2AD000)' not in tm
            or 'return *(int *)((int)A_0C2AD000)' not in tm or '((unsigned char *)((int)A_0C2AD000))' not in tn):
        bad.append('macro: a mod\'s pointer-cast macro is the symbol itself (an address constant for a file-scope initializer), anything else and the decomp\'s own files keep the int cast:\n' + tm + tn)
    pieces = [(0x0C010000, '_f1'), (0x0C010100, '_f2'), (0x0C010200, '_d3'), (0x0C010300, '_f4')]
    syms = {'_f1': 0x8C010000, '_f2': 0x8C010400, '_d3': 0x8C010800, '_bss': 0x8C020000, '_f4__2': 0x8C030000}
    cfun = {0x0C010100: 'f2', 0x0C010300: 'f4'}
    new = M.mapper(pieces, {1, 3}, {3: '__2'}, syms, cfun, 0x0C010400, 0x0C100000, 0x80000000)
    for v, want in ((0x8C010208, 0x8C010808), (0x0C010208, 0x0C010808), (0x8C010100, 0x8C010400), (0x8C010310, 0x8C030010),
                    (0x8C010110, None), (0x8C010410, 0x8C020010)):
        if new(v) != want:
            bad.append('map: %08X -> %r, want %r' % (v, None if new(v) is None else '%08X' % new(v), None if want is None else '%08X' % want))
    piece = ('          .IMPORT     _g\n          .EXPORT     _f\n_f:\n          .DATA.W     H\'4F22\n          BSR         _g\n'
             '          .DATA.W     H\'0009\n          .DATA.L     _f+H\'8\n          .END')
    raw = {0x0C010000: 0x4F22, 0x0C010002: 0xB123, 0x0C010004: 0x0009}
    d = M.data_copy(piece, '_f', 0x0C010000, lambda a: raw[a])
    if '_f__d:' not in d or '.EXPORT     _f__d' not in d or "_f__d+H'8" not in d or 'BSR' in d or ".DATA.W     H'B123" not in d:
        bad.append('data copy: want label _f__d, its self pointer _f__d+H\'8 and the bsr back as H\'B123:\n' + d)
    hp = ('          .SECTION    P, CODE, ALIGN=2\n          .IMPORT     _vecMake\n          .EXPORT     _g\n_g:\n          .DATA.W     H\'4F22\n'
          '          .DATA.W     H\'0009\n          .DATA.L     _vecMake\n          .DATA.W     H\'0000\n          .END')
    raw_h = {0x0C020000: 0x4F22, 0x0C020002: 0x0009}
    h = M.hole_text(hp, '_g', 0x0C020000, lambda a: raw_h[a])
    if '.DATA.L     _vecMake' not in h or '_g__h:' not in h or '__d' in h or "H'0000\n" in h.replace("          .DATA.W     H'0000\n          .END", ''):
        bad.append('hole: a replaced piece keeps its pool word (.DATA.L _vecMake) and its label is _g__h, not zeros:\n' + h)
    got = M.hole_pieces([0, 4], 8, {0, 2, 3, 5, 6}, {6})
    if got != {5}:
        bad.append('holes: group 0-3 has kept piece 1 only (nothing between kept pieces: no hole) and group 4-7 has kept 4 and 7 with 5 replaced '
                   'and 6 in the filler: the hole is 5 alone, got %r' % sorted(got))
    if M.hole_pieces([0, 3], 6, {0, 1, 2, 3, 4, 5}, set()):
        bad.append('holes: a group with no kept piece has no hole')
    run = ('          .EXPORT     _f__2\n_f__2:\n          BSR         _g\n          .DATA.W     H\'0009\n'
           '          BRA         _h__2+H\'4\n          .DATA.W     H\'0009\n          .END')
    v, vs = M.veneers(run, {'_f__2', '_h__2'}, '_f__2')
    if 'BSR         _f__2__v1' not in v or '.IMPORT     _f__2__v1' not in v or "BRA         _h__2+H'4" not in v \
            or not vs or 'ALIGN=4' not in vs or '.DATA.L     _g' not in vs or '.EXPORT     _f__2__v1' not in vs:
        bad.append('veneer: the bsr out of the group goes through _f__2__v1, in a file of its own (ALIGN=4); the bra inside '
                   'the group stays:\n%s\n----\n%s' % (v, vs))
    import tempfile
    d = tempfile.mkdtemp()
    open(d + '/a.src', 'w').write('          .SECTION    P, CODE, ALIGN=2\n          .IMPORT     _b\n          .IMPORT     _z\n'
                                  '          .EXPORT     _a\n_a:\n          .DATA.L     _b\n          .END\n')
    open(d + '/b.src', 'w').write('          .SECTION    P, CODE, ALIGN=2\n          .EXPORT     _b\n_b:\n          .DATA.W     H\'1234\n          .END\n')
    u = M.unit_source([d + '/a.src', d + '/b.src'], 6)
    if 'ALIGN=4' not in u or '.IMPORT     _z' not in u or '.IMPORT     _b' in u or u.count(".DATA.W     H'0000") != 3 \
            or u.index("H'0000") > u.index('_a:') or u.count('.END') != 1 or u.index('_a:') > u.index('_b:'):
        bad.append('unit: two pieces as one ALIGN=4 object with 6 pad bytes in front, _b not imported (defined inside), one .END:\n' + u)
    m = ('ATTRIBUTE  :   CODE  NOSHR\n\nP                                 H\'8C010000  -  H\'8C01000F  H\'00000010\n'
         '              u00000                           u00000                          \n'
         '                                  H\'8C010010  -  H\'8C010013  H\'00000004\n'
         '              gen_a                            gen_a                           \n')
    open(d + '/t.map', 'w').write(m)
    mm = M.map_modules(d + '/t.map')
    if mm != {'u00000': (0x0C010000, 0x0C010010), 'gen_a': (0x0C010010, 0x0C010014)}:
        bad.append('map_modules: %r' % mm)
    keep = M.mapper(pieces, {1, 3}, {3: '__2'}, syms, cfun, 0x0C010400, 0x0C100000, 0x80000000, keep=(0x0C010200, 0x0C010300))
    if keep(0x8C010208) != 0x8C010208 or keep(0x8C010100) != 0x8C010400:
        bad.append('keep: an address in the kept range stays (%08X), one outside still maps' % keep(0x8C010208))
    unit = ('          .SECTION    P, CODE, ALIGN=4\n          .IMPORT     _far\n          .IMPORT     _near\n          .EXPORT     _k\n_k:\n'
            '          .DATA.W     H\'0009\n          BSR         _near\n          .DATA.W     H\'0009\n          BSR         _far\n          .END')
    v2, vs2 = M.veneers(unit, set(), '_u00007', only={6}, start=2)
    if 'BSR         _near' not in v2 or 'BSR         _u00007__v3' not in v2 or not vs2 or '.DATA.L     _far' not in vs2 or '_near' in vs2:
        bad.append('only: the bsr at byte 6 (_far) goes through _u00007__v3 (numbering from 2), the one at byte 2 stays:\n%s\n----\n%s' % (v2, vs2))
    items = [('f', 0x0C010000, 0x0C010008, 0x0C010030), ('g', 0x0C010100, 0x0C010108, 0x0C010120)]
    where = lambda a: {0x0C010000: 0x0C020000, 0x0C010008: 0x0C020008, 0x0C010030: 0x0C020030, 0x0C010100: 0x0C020100,
                       0x0C010108: 0x0C020108, 0x0C010120: 0x0C020140}.get(a)       # g's target moved 0x20 more than g did
    word = lambda a: {0x0C020008: 0x2C, 0x0C020108: 0x1C}[a]       # f: 0x0C020000 + 4 + 0x2C = its target; g: unchanged distance 0x1C
    w = M.wrong_distance_targets(items, where, word)
    if [x[0] for x in w] != ['g'] or w[0][2] != 0x0C020100 + 4 + 0x1C or w[0][3] != 0x0C020140:
        bad.append('distance: only g (its target is 0x20 farther in the build) is wrong: %r' % w)
    # bsspad: the BSS block keeps its original alignment modulo 32 (Virtua Tennis: _bss at 8C279530 for an image end of 8C20D1D4 moved
    # every object by 28 mod 32; the Maple DMA buffer 8C472080, 32-byte aligned, became 8C4DE8DC and the console reset on the controller scan)
    end_, start_ = 0x8C20D1D4, 0x8C279530
    pad = M.bss_pad(end_, start_)
    if pad != 4 or (start_ + pad - end_) % 32:
        bad.append('bsspad: pad %d for end %08X and block start %08X, want 4 (so that _bss - end is a multiple of 32)' % (pad, end_, start_))
    for st in (0x8C279530, 0x8C279534, 0x8C27953C, 0x8C279520, 0x8C20D1D4):
        pd = M.bss_pad(end_, st)
        if not 0 <= pd < 32 or (st + pd - end_) % 32:
            bad.append('bsspad: start %08X gives pad %d, _bss - end = %d mod 32' % (st, pd, (st + pd - end_) % 32))
    txt = M.bss_text(end_, 0x8C480000, pad)
    lines_ = [l.split() for l in txt.split('\n') if l.strip() and not l.strip().startswith(';')]
    if lines_[1][0] != '.RES.B' or lines_[1][1] != "H'4" or lines_[2] != ['.EXPORT', '_bss'] or lines_[3] != ['_bss:']:
        bad.append('bsspad: the pad must come before the _bss label, then the block:\n' + txt)
    if "H'%X" % (0x8C480000 - end_) not in txt:
        bad.append('bsspad: the block size lost:\n' + txt)
    if '.RES.B      H' in M.bss_text(end_, 0x8C480000, 0).split('_bss:')[0]:
        bad.append('bsspad: a zero pad must write no pad line')
    import layout as L
    for e_, want in ((0x8C20D1D4, 0x8C20D1D4), (0x0C9E293F, 0x0C9E2940), (0x0C9E2941, 0x0C9E2944), (0x0C9E2940, 0x0C9E2940)):
        if L.bss_start(e_) != want:
            bad.append('bss_start: %08X -> %08X, want %08X (an image that ends on a word keeps its end)' % (e_, L.bss_start(e_), want))
    region0 = L.region
    L.region = lambda name, required=False: (1, None) if name == 'mixed' else ((0, None) if name == 'off' else None)
    try:
        if not L.flag('mixed') or L.flag('off') or L.flag('absent'):
            bad.append('flag: `mixed 1` is on, `off 0` and a missing line are off')
    finally:
        L.region = region0
    for v, want in ((0xAC210C5A, '0AC210C5A'), (0x8C2FC69C, '8C2FC69C'), (0x0C010000, '0C010000'), (0xFFFFFFFF, '0FFFFFFFF'), (0x9FFFFFFF, '9FFFFFFF')):
        if M.lnk_hex(v) != want:
            bad.append('lnk_hex: %08X -> %s, want %s (a value that starts with a letter needs a leading 0 or the linker reads a symbol)' % (v, M.lnk_hex(v), want))
    if M.split_routes([10, 1999, 2000, 4000], True) != ([10, 1999], [2000, 4000]) or M.split_routes([10, 1999, 2000], False) != ([], [10, 1999, 2000]):
        bad.append('routes: offsets under 2000 go before the unit only when allowed: %r %r' % (M.split_routes([10, 1999, 2000, 4000], True), M.split_routes([10, 1999, 2000], False)))
    B0 = 0x0C010000
    words = {B0: 0x8B10, B0 + 0x5C: 0x8B04, B0 + 0x80: 0xB010}           # bf from +00 lands at +24 (group 1); bf from +5C at +6C (group 3 from 2); a bsr is no tie
    gof = lambda a: (a - B0) // 0x20
    ties = M.cond_ties([(B0, 0x100)], lambda a: words.get(a, 0x0009), set(), B0 + 0x100, B0, gof)
    if ties != {(0, 1), (2, 3)}:
        bad.append('cond_ties: %r, want the groups {(0, 1)} and {(2, 3)}' % sorted(ties))
    if M.cond_ties([(B0, 0x100)], lambda a: words.get(a, 0x0009), {B0, B0 + 0x5C}, B0 + 0x100, B0, gof):
        bad.append('cond_ties: a pool word is no instruction')
    for g_, ts_, want in ((1, {(1, 3), (3, 4)}, (1, 4)), (1, {(5, 6)}, (1, 1)), (2, {(0, 2)}, (0, 2)), (0, set(), (0, 0)), (4, {(1, 3), (3, 4)}, (1, 4))):
        if M.copy_extent(g_, ts_) != want:
            bad.append('copy_extent: group %d with ties %r -> %r, want %r' % (g_, sorted(ts_), M.copy_extent(g_, ts_), want))
    hole = ('; hole\n          .SECTION    P, CODE, ALIGN=2\n          .IMPORT     _g\n          .EXPORT     _f__h\n_f__h:\n'
            + ''.join("          .DATA.W     H'%04X\n" % (0x1000 + i) for i in range(8)) + '          .END')

    def nbytes(t_):
        n_ = 0
        for l_ in t_.split('\n'):
            m_ = l_.split()
            if m_[:1] in (['.DATA.W'],) or (m_ and m_[0] in ('MOV.L', 'JMP', 'NOP')):
                n_ += 2
            elif m_[:1] == ['.DATA.L']:
                n_ += 4
        return n_
    for st_, pad_ in ((0x0C010100, 1), (0x0C010102, 2)):
        t_, ok_ = M.tramp_text(hole, '_f', st_, 16, set())
        lines_ = [l.strip() for l in t_.split('\n')]
        if not ok_ or nbytes(t_) != 16 or 'MOV.L       LTf,R0' not in lines_ or 'JMP         @R0' not in lines_ \
                or lines_.count(".DATA.W     H'0009") != pad_ or 'LTf:' not in lines_ or '.DATA.L     _f' not in lines_ \
                or lines_.index('.IMPORT     _f') > lines_.index('.EXPORT     _f__h') or lines_[-1 - len(range(5 + pad_, 8)):-1] != [".DATA.W     H'%04X" % (0x1000 + i) for i in range(5 + pad_, 8)]:
            bad.append('tramp: start %08X (%d pad word(s)): %s, %d bytes, want 16 with the pool word aligned:\n%s' % (st_, pad_, ok_, nbytes(t_), t_))
    if M.tramp_text(hole, '_f', 0x0C010100, 8, set()) != (hole, False):
        bad.append('tramp: a hole shorter than 12 bytes is left as it is')
    if M.tramp_text(hole, '_f', 0x0C010100, 16, {0x0C010104}) != (hole, False):
        bad.append('tramp: a pool word of a neighbour in the first 12 bytes keeps the hole as it is')
    if M.tramp_text(hole.replace("          .DATA.W     H'1002\n          .DATA.W     H'1003\n", "          .DATA.L     _g\n"), '_f', 0x0C010100, 16, set())[1]:
        bad.append('tramp: a long word (a pool word) among the first 12 bytes keeps the hole as it is')
    src = ["          BT          _f", "          BT/S        _f+H'4", "          BSR         _g", "          BRA         _f", "          BSR         _h", "          .DATA.L     _f"]
    out_, hit_ = M.retarget_branches(src, {'_f', '_g'}, {'_f'})
    want_ = ["          BT          _f__h", "          BT/S        _f__h+H'4", "          BSR         _g", "          BRA         _f__h", "          BSR         _h", "          .DATA.L     _f"]
    if out_ != want_ or hit_ != {'_f__h'}:
        bad.append('retarget: conditional branches into any hole, calls only into a callable hole, words and other calls untouched:\n' + '\n'.join(out_) + '\n' + repr(hit_))
    if M.retarget_branches(src, set(), set()) != (src, set()):
        bad.append('retarget: with no holes nothing changes')
    # fit_text: the build's last line states the gap, so nobody works it out from the two addresses
    for hi, fixed, want in ((0x0CA22C00, 0x0CA10000, 'DOES NOT FIT: 76,800 bytes (75.0 KB) over fixed'),
                            (0x0CA0F000, 0x0CA10000, 'fits, 4,096 bytes spare below fixed'),
                            (0x0CA10000, 0x0CA10000, 'DOES NOT FIT: 0 bytes spare, the image must end below fixed'),
                            (0x0CA10001, 0x0CA10000, 'DOES NOT FIT: 1 bytes (0.0 KB) over fixed')):
        got = M.fit_text(hi, fixed)
        if got != want:
            bad.append('fit_text(%08X, %08X): %r, wanted %r' % (hi, fixed, got, want))
    if bad:
        sys.exit('[ERROR] mbuild check failed:\n' + '\n'.join(bad))
    print('[mbuild] ok: address numbers become symbols; each lands in its piece, C function, second copy or the BSS block')


if __name__ == '__main__':
    main()
