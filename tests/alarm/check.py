#!/usr/bin/env python3
"""Step 5's time limits hold (scripts/tools/5-generated/gen_equiv/__main__.py). No game data. Stdlib only.

The reading and drawing limits are one SIGALRM each, raising Timeout. When Timeout was an Exception, any `except Exception` inside the
tools (gen_drv.mend, directed, the reader's fallbacks) took it, the alarm never fired again and drawing ran on: cpuSglAimTable (Virtua
Tennis) drew for 106 minutes against an alarm of 38.

    check.py      swallow   the alarm firing inside an `except Exception` still stops the work, within a second of the limit
                  caught    _read and _draw catch Timeout and report it ('timeout', 'Timeout')
"""
import os
import re
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '5-generated', 'gen_equiv', '__main__.py')


def main():
    src = open(MAIN).read()
    bad = []
    m = re.search(r'^class Timeout\(.*$', src, re.M)
    g = {}
    exec(m.group(0) + '\ndef _alarm(sig, frm): raise Timeout()\n', g)
    signal.signal(signal.SIGALRM, g['_alarm'])
    t = time.time(); stopped = False
    signal.alarm(1)
    try:
        while time.time() - t < 5:
            try:
                sum(range(10000))
            except Exception:
                pass                                  # a tool's own fallback
    except g['Timeout']:
        stopped = True
    finally:
        signal.alarm(0)
    if not stopped or time.time() - t > 2:
        bad.append('swallow: an alarm inside `except Exception` did not stop the work (%.1f s)' % (time.time() - t))
    for fn, want in (('_read', r'except Timeout'), ('_draw', r'except \([^)]*Timeout[^)]*\)|except Timeout')):
        body = re.search(r'^def %s\(.*?(?=^\S)' % fn, src, re.M | re.S)
        if not body or not re.search(want, body.group(0)):
            bad.append('caught: %s does not catch Timeout' % fn)
    if bad:
        sys.exit('[ERROR] alarm check failed:\n' + '\n'.join(bad))
    print('[alarm] ok: the step-5 alarm stops work through the tools\' own except Exception, and is reported')


if __name__ == '__main__':
    main()
