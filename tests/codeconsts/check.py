#!/usr/bin/env python3
"""C that reads a float from the original's code by its address must become the constant (scripts/tools/8-build/codeconsts.py). The
build from C puts its own code over the original's game and fill regions, so `*(float *)0xC057A4C` read there takes whatever the new
code has (Crazy Taxi: Init_SEGA_LOGO's 500.0 read the address of nlPushUnitMatrix, and the game froze before the SEGA logo). No game
data, no compiler. Stdlib only.

    check.py      scan() and literal() on a synthetic image (base 0C010000, regions game 0C020000-0C030000):
                    inside     a read of a word inside a replaced region is found, with the constant the image holds there
                    outside    a read outside every replaced region (0C030000, the first word after the game code; the data, the SDK) is left alone
                    store      `*(float *)0xC020040 = ...` is a store into the code, not a constant: left alone
                    unaligned  an address that is not a word is left alone
                    parens     `x = (*(float *)A);` is replaced with its parentheses, `(a * (*(float *)A))` keeps the one that is
                               the expression's own
                    literal    the shortest decimal that gives the same bits back: 500.0, 0.5, a negative one in parentheses,
                               1/3 exactly; NaN and an infinity have no constant (None)
"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools'))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '8-build'))
import codeconsts  # noqa: E402

BASE = 0x0C010000
REGS = [(0x0C020000, 0x0C030000)]


def image():
    img = bytearray(0x30100)
    for a, v in ((0x0C020040, 500.0), (0x0C020044, -1.5), (0x0C020048, 0.5), (0x0C030000, 2.0)):
        struct.pack_into('<f', img, a - BASE, v)
    struct.pack_into('<f', img, 0x0C0200F0 - BASE, 1.0 / 3.0)
    return bytes(img)


def bits(lit):
    """the float a C literal written by literal() stands for"""
    s = lit.strip('()')
    return struct.pack('<f', float(s[:-1]))


def main():
    img = image()
    bad = []

    def find(text):
        return codeconsts.scan(text, img, BASE, REGS)

    t = 'x = *(float *)0xC020040;\n'
    h = find(t)
    if len(h) != 1 or bits(h[0][3]) != struct.pack('<f', 500.0):
        bad.append('inside: a read of 0C020040 (500.0) is not found as that constant: %s' % h)
    elif t[:h[0][0]] + h[0][3] + t[h[0][1]:] != 'x = %s;\n' % h[0][3]:
        bad.append('inside: the span replaced is not exactly the read: %r' % t[h[0][0]:h[0][1]])

    if find('x = *(float *)0xC030000;\n') or find('x = *(float *)0xC1EE788;\n'):
        bad.append('outside: a read outside the replaced regions was found')

    if find('*(float *)0xC020040 = 1.0f;\n'):
        bad.append('store: a store into the code was taken for a constant')

    if find('x = *(float *)0xC020042;\n'):
        bad.append('unaligned: an address that is not a word was found')

    t = 'x = (*(float *)0xC020044);\n'
    h = find(t)
    if len(h) != 1 or t[:h[0][0]] + h[0][3] + t[h[0][1]:] != 'x = %s;\n' % h[0][3]:
        bad.append('parens: a parenthesised read is not replaced whole: %s' % h)
    t = 'y = (a * (*(float *)0xC020048));\n'
    h = find(t)
    new = t[:h[0][0]] + h[0][3] + t[h[0][1]:] if h else ''
    if new != 'y = (a * %s);\n' % (h[0][3] if h else ''):
        bad.append('parens: the closing parenthesis of the outer expression was eaten: %r' % new)

    lit = codeconsts.literal
    for v in (500.0, 0.5, -1.5, 1.0 / 3.0, 100.0, 0.099999994):
        b = struct.pack('<f', v)
        s = lit(struct.unpack('<I', b)[0])
        if s is None or bits(s) != b:
            bad.append('literal: %r does not give the same bits back (%s)' % (v, s))
    if not lit(struct.unpack('<I', struct.pack('<f', -1.5))[0]).startswith('('):
        bad.append('literal: a negative constant is not in parentheses')
    if lit(0x7FC00000) is not None or lit(0x7F800000) is not None:
        bad.append('literal: NaN or an infinity got a constant')

    if not bad:
        print('[codeconsts] ok: a float read from the replaced code becomes its constant, exactly; reads outside, stores, unaligned addresses are left alone; parentheses kept right')
        return
    sys.exit('[ERROR] codeconsts check failed:\n' + '\n'.join(bad))


if __name__ == '__main__':
    main()
