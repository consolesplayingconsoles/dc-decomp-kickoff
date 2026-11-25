"""The size gate on `frame` for the generator (gen_drv.build, GEN_FRAME=gate). Stdlib only, no game data (tested without a game repo:
tests/test_gen_framegate.py).

frame.scalarize writes frame slots read and written as one scalar as locals, which SHC keeps in registers. It was the biggest kept
gain of the Power Stone 2 shrink batches (5,076 of 6,598 bytes over 138 units) and can make a function much bigger (4,784 to
10,064), so it is not on for every function. The generator builds a function without it and with it, compiles both and keeps the
smaller: the same gate shrink.py applies to every rewrite, here at birth. GEN_FRAME: 0 or unset, never; 1, always (as before);
gate, per function by size.
"""
import os


def build_gated(build, size, name, ret, passthru=False):
    """(text, c) from build(name, ret, passthru): under GEN_FRAME=gate, the smaller of the plain and the framed C by size(name, text,
    c) (None: it does not compile); the plain C on a tie, when the framed build fails, or when neither is measurable."""
    if os.environ.get('GEN_FRAME', '0') != 'gate':
        return build(name, ret, passthru)
    try:
        os.environ['GEN_FRAME'] = '0'
        plain = build(name, ret, passthru)
        os.environ['GEN_FRAME'] = '1'
        try:
            framed = build(name, ret, passthru)
        except Exception:
            return plain
    finally:
        os.environ['GEN_FRAME'] = 'gate'
    if framed[0] == plain[0]:
        return plain
    n_plain = size(name, plain[0], plain[1])
    n_framed = size(name, framed[0], framed[1])
    if n_framed is None:
        return plain
    if n_plain is None or n_framed < n_plain:
        return framed
    return plain
