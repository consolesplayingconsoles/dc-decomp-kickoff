#!/usr/bin/env python3
"""A buffer in the frame handed to a call (scripts/tools/sh4sim.py, equiv.same) on synthetic functions, no game data. Stdlib only.

    check.py      each function fills a local buffer and calls f(buffer): the callee's input is the buffer's contents.
                    contents  7 against 9 in the first word: the two runs must not agree (Virtua Tennis cursorBoxPut: its four
                              vertices go to nlDispStripTexOfsTrnsl in its frame; C that dropped two words of the position passed)
                    layout    the same contents at another offset in the frame: they agree (the frame is the compiler's business)
                    saves     one side also saves r8: they agree (the saved registers are not the buffer)
                    selfcopy  one side copies a word the function never set onto itself: they agree (the flat form's self-copies)
                    neighbour one side also stores another local two words past the buffer: they agree
                    adjacent  one side stores another local right after the buffer, where the other has a slot it does not
                              store (an output): they agree (Virtua Tennis shadowVolBuildPoint: after the vector it passes, the C
                              keeps another vector, the original the callee's output)
                    earlier   a word stored before an earlier call is not part of the buffer the next call gets
"""
import os
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401
import sh4sim  # noqa: E402
import equiv  # noqa: E402

BASE = 0x8C010000
CALLEE = BASE + 0x100


def run(words):
    """words: the body; a mov.l @(pool),r1 placeholder 'POOL' loads the callee's address."""
    words = list(words)
    pool_at = (2 * len(words) + 3) & ~3
    for tag in ('POOL', 'POOL2'):
        if tag in words:
            i = words.index(tag)
            pc = BASE + 2 * i
            words[i] = 0xD100 | ((BASE + pool_at - ((pc & ~3) + 4)) // 4)
    code = b''.join(struct.pack('<H', w) for w in words)
    code += b'\x09\x00' * ((pool_at - len(code)) // 2) + struct.pack('<I', CALLEE)
    code += b'\x09\x00' * ((CALLEE - BASE - len(code)) // 2) + struct.pack('<HH', 0x000B, 0x0009)
    d = tempfile.mkdtemp()
    open(os.path.join(d, 'exe.bin'), 'wb').write(code)
    return sh4sim.run({'about': 'stackbuf', 'poke': {}, 'exe': 'exe.bin', 'base': '%08X' % BASE, 'entry': '%08X' % BASE,
                       'end': '%08X' % (BASE + CALLEE - BASE)}, d)


def fn(value, at=0, save_r8=False, selfcopy=False, neighbour=False, adjacent=None, earlier=None):
    """sts.l pr,@-r15 [mov.l r8,@-r15] / add #-16,r15 / mov #value,r0 / mov r15,r4 / add #at,r4 / mov.l r0,@r4
    [mov.l @(12,r15),r2 / mov.l r2,@(12,r15)] / mov.l @(pool),r1 / jsr @r1 / nop / add #16,r15 [mov.l @r15+,r8] / lds.l @r15+,pr / rts / nop"""
    w = [0x4F22] + ([0x2F86] if save_r8 else []) + [0x7FF0, 0xE000 | value, 0x64F3, 0x7400 | at, 0x2402]
    if selfcopy:
        w += [0x52F3, 0x1F23]
    if neighbour:
        w += [0xE205, 0x1F22]                 # mov #5,r2 / mov.l r2,@(8,r15): a local two words past the buffer
    if adjacent is not None:
        w += [0xE200 | adjacent, 0x1F21]      # mov #adjacent,r2 / mov.l r2,@(4,r15): a local right after the buffer
    if earlier is not None:                   # mov #earlier,r2 / mov.l r2,@(4,r15) / a call (the word goes in before it)
        w = w[:1] + [0x7FF0, 0xE200 | earlier, 0x1F21, 'POOL', 0x410B, 0x0009, 0x7F10] + w[1:]
    w += ['POOL2' if earlier is not None else 'POOL', 0x410B, 0x0009, 0x7F10] + ([0x68F6] if save_r8 else []) + [0x4F26, 0x000B, 0x0009]
    return run(w)


def agree(a, b):
    for r in (a, b):
        if r['error']:
            return None, r['error']
    return equiv.same(a, b, [], {}, {CALLEE & 0x1FFFFFFF | 0x0C000000: (1, 0)})


def main():
    bad = []
    ok, why = agree(fn(7), fn(9))
    if ok is not False:
        bad.append('contents: 7 against 9 in the buffer passed to the call agree (%s)' % why)
    ok, why = agree(fn(7), fn(7, adjacent=4))
    if ok is not True:
        bad.append('adjacent: a local right after the buffer on one side only does not agree: %s' % why)
    ok, why = agree(fn(7, earlier=3), fn(7, earlier=4))
    if ok is not True:
        bad.append('earlier: a word stored before an earlier call counts as the buffer: %s' % why)
    for name, other in (('layout', fn(7, at=8)), ('saves', fn(7, save_r8=True)), ('selfcopy', fn(7, selfcopy=True)), ('neighbour', fn(7, neighbour=True))):
        ok, why = agree(fn(7), other)
        if ok is not True:
            bad.append('%s: the same buffer contents do not agree: %s' % (name, why))
    if bad:
        sys.exit('[ERROR] stackbuf check failed:\n' + '\n'.join(bad))
    print('[stackbuf] ok: a frame buffer passed to a call is compared by its contents, not by its place or the saved registers')


if __name__ == '__main__':
    main()
