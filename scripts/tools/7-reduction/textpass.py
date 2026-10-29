#!/usr/bin/env python3
"""Apply a text pass to the C a function has now, without writing it again, and keep it only when it compiles smaller and the function
still passes in its file. Run in the repo, alone (it rewrites src/ and tests/equivalent.txt).

    python3 tools/7-reduction/textpass.py register <name> ...

A pass changes how the C is written, not what it does. `register` declares the function's scalar locals register
(gen_drv.register_locals): written again by the generator the same function can come out bigger than it is (entryGridDrawCursors,
Virtua Tennis: 7,180 bytes as it is, 7,416 written again, 5,636 as it is with register), so a regeneration misses what the pass alone gives.
For each name: the current C and the passed C are compiled alone (tools/sizes.py); a smaller one replaces the old in its file, the file is
checked with tools/equiv.py and the old C goes back unless the function is EQUIVALENT. One line per function in build/textpass.log.
"""
import os as _tp_os, sys as _tp_sys  # noqa: E401  every tools folder on the import path (tools/toolpath.py)
_tp_sys.path.insert(0, _tp_os.path.normpath(_tp_os.path.join(_tp_os.path.dirname(_tp_os.path.abspath(__file__)), '..')))
import toolpath  # noqa: E402,F401
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '5-generated', 'gen_equiv'))
LOG = os.path.join('build', 'textpass.log')


def passes():
    import gen_drv
    return {'register': gen_drv.register_locals}


def where(fn):
    import consistency
    import glob
    for f in sorted(glob.glob('src/*.c')):
        if os.path.basename(f).startswith(('zz_', 'gen_tmp')):
            continue
        try:
            t = open(f, errors='replace').read()
        except OSError:
            continue
        b = consistency.block(t, fn)
        if b:
            return f, t, b
    return None, None, None


def checked(path, fn):
    """the function's line of tools/equiv.py on its file: EQUIVALENT or not"""
    out = subprocess.run(['python3', 'tools/equiv.py', path, fn], capture_output=True, text=True)
    m = re.search(r'^%s\s+(\S+).*$' % re.escape(fn), out.stdout, re.M)
    return (m.group(1) if m else 'no result'), (m.group(0) if m else (out.stdout + out.stderr).strip()[-160:])


def apply_one(fn, pas, size_of, check, log):
    """(new size or None, reason): the pass on fn's current C, kept when smaller and still EQUIVALENT"""
    path, text, b = where(fn)
    if not path:
        return None, 'no C'
    old = text[b[0]:b[1]]
    new = pas(old)
    if new == old:
        return None, 'nothing to change'
    a, n = size_of(fn, old, text), size_of(fn, new, text)
    if a is None or n is None:
        return None, 'not measurable (%s -> %s)' % (a, n)
    if n >= a:
        return None, 'not smaller (%s -> %s)' % (a, n)
    open(path, 'w').write(text[:b[0]] + new + text[b[1]:])
    verdict, line = check(path, fn)
    if verdict != 'EQUIVALENT':
        open(path, 'w').write(text)            # the old C back
        check(path, fn)                        # and its pass recorded again
        return None, 'failed, old C back: %s' % line
    return n, 'SHRUNK %s -> %s' % (a, n)


def main(argv):
    if len(argv) < 3 or argv[1] not in passes():
        sys.exit(__doc__)
    import sizes
    pas = passes()[argv[1]]
    os.makedirs('build', exist_ok=True)
    log = open(LOG, 'a')
    size_of = lambda fn, c, unit: sizes.c_size_any(fn, c, [], sizes.unit_head(unit))
    for fn in argv[2:]:
        n, why = apply_one(fn, pas, size_of, checked, log)
        log.write('%s %s %s\n' % (fn, why, time.strftime('%H:%M:%S')))
        log.flush()
    log.write('done %s\n' % time.strftime('%H:%M:%S'))


if __name__ == '__main__':
    main(sys.argv)
