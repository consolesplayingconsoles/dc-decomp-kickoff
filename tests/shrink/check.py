#!/usr/bin/env python3
"""What the shrink logs when a regenerated function fails its recheck (scripts/tools/ledger.py last_failure, scripts/tools/7-reduction/shrink.py),
with no game data and no compiler. Stdlib only.

    check.py      a temp repo with a state/results.jsonl as the recheck writes it:
                    failure   the latest DIFFERS row of the function is returned with its case text, so the shrink's log names
                              the failing case instead of the last three lines of counts (Crazy Taxi: 93 restored functions were
                              logged as "1 pass 0, 1 differ" and the reason had to be dug out by hand)
                    compile   a "did not compile" row counts as a failure too
                    old       a row older than the recheck is not this recheck's (the function failed in an earlier run)
                    pass      EQUIVALENT rows and other functions' rows are not failures
                    none      no file, or no row: None
                    source    shrink.py writes the failing C to build/shrink-failed/<function>.c and logs it
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401
import ledger  # noqa: E402


def main():
    tmp = tempfile.mkdtemp()
    cwd = os.getcwd()
    bad = []
    try:
        os.chdir(tmp)
        if ledger.last_failure('f', '') is not None:
            bad.append('none: no results file gave a failure')
        os.makedirs('state')
        rows = [
            {'t': '2026-10-23T18:00:00', 'fn': 'f', 'outcome': 'DIFFERS', 'detail': 'case 9: old'},
            {'t': '2026-10-23T18:44:24', 'fn': 'f', 'outcome': 'DIFFERS', 'detail': 'case 1: error: original null / C "more than 2000000 instructions"'},
            {'t': '2026-10-23T18:45:00', 'fn': 'f', 'outcome': 'EQUIVALENT', 'detail': 'rechecked from state/kept'},
            {'t': '2026-10-23T18:46:00', 'fn': 'g', 'outcome': 'DIFFERS', 'detail': 'case 2: other function'},
            {'t': '2026-10-23T18:47:00', 'fn': 'h', 'outcome': 'did not compile', 'detail': 'Scalar required for "!"'},
        ]
        with open('state/results.jsonl', 'w') as fh:
            fh.write('not json\n' + ''.join(json.dumps(r) + '\n' for r in rows))
        want = {'failure': (('f', '2026-10-23T18:44:00'), ('DIFFERS', 'case 1: error: original null / C "more than 2000000 instructions"')),
                'compile': (('h', ''), ('did not compile', 'Scalar required for "!"')),
                'old': (('f', '2026-10-23T18:50:00'), None),
                'pass': (('k', ''), None)}
        for k, (args, w) in want.items():
            got = ledger.last_failure(*args)
            if got != w:
                bad.append('%s: got %s, want %s' % (k, got, w))
        src = open(os.path.join(TOOLS, '7-reduction', 'shrink.py')).read()
        for needle in ("ledger.last_failure(fn, since)", "'shrink-failed'", "new C failed, old restored"):
            if needle not in src:
                bad.append('source: shrink.py does not contain %s' % needle)
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp, ignore_errors=True)
    if bad:
        sys.exit("[ERROR] shrink check failed:\n" + "\n".join(bad))
    print("[shrink] ok: a restored function's log line carries the recheck's failing case and names the file with the new C")


if __name__ == '__main__':
    main()
