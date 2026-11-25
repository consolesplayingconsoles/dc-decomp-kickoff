"""secondpass.py: what a run says at its end about the functions whose draw timed out.

A draw has a time limit (max(60, size/8) s times GEN_TIME_FACTOR). It is CPU time: a function with big call answers cost 395 s of CPU
against the 60 s floor, and a quiet machine does not shorten it. The first pass keeps the short limit so a function that really hangs
cannot hold the run; the functions that timed out are tried again alone with a longer limit, smallest first. Only those: a function the
original never finishes on, or that the reader skips, does not change with more time.

    hint(records, size)    the lines to print: records are the (kind, name, reason) tuples of the functions not drawn, size(name) its bytes
"""

FACTOR = 8


def timed_out(records):
    """the names whose reason is a draw timeout"""
    return [r[1] for r in records if len(r) > 2 and str(r[2]).strip().startswith('Timeout')]


def hint(records, size):
    names = sorted(set(timed_out(records)), key=lambda n: (size(n), n))
    if not names:
        return []
    limit = max(size(n) for n in names)
    return ['[second pass] %d function(s) timed out while drawing. A draw is CPU time, not load: try them again alone, with a longer limit, '
            'smallest first:' % len(names),
            'GEN_TIME_FACTOR=%d python3 tools/5-generated/gen_equiv --jobs 1 %d %s' % (FACTOR, limit, ' '.join(names))]
