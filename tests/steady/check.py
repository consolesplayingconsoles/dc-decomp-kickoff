#!/usr/bin/env python3
"""A run cut at the step limit that has stopped changing (scripts/tools/5-generated/gen_equiv/directed.py steady_state, wired into
gen_drv), with the real simulator on synthetic code. No game data, no compiler. Stdlib only.

Crazy Taxi proved its functions that never end in the simulator (bootMain, MainLoop, kmiInitializeDevice, vmsfs_c_dispatch...) with
cases marked endless, written by hand: both sides run to the step limit and the check compares the calls and writes made so far.
Drawing found them by running a retry at 20,000,000 instructions, minutes for one run, so a function that really never ends timed out
(Virtua Tennis main, vmsfs_c_dispatch, kmyInitializeHardware). steady_state tells the two apart on the trace of the capped run: the same
pc with the same registers twice, and the same stores in the cycle between, is a fixed cycle.

    check.py      poll      loop: r3 = *G; cmp/hs 21,r3; bf out; bra loop with G = 25: steady
                  count     dt r5 / bf loop with r5 = 0x7FFFFFFF: not steady (the registers change on every pass)
                  cut       two sides of an endless case cut at the step limit are compared on the same number of calls AND device
                            accesses (equiv.cut_endless): compiled code gets through fewer passes of the loop in the same steps, so its
                            device accesses run out sooner (Virtua Tennis vmsfs_c_dispatch: "access 1053/1333: original [...] / C none")
                  declared  a function listed in endless.txt (one name per line, # comments: a game loop whose only change from pass to pass
                            is a counter, Virtua Tennis main; Crazy Taxi MainLoop) has its capped cases taken as endless without the
                            steady-state test, which a counter fails. gen_drv.declared_endless reads the list
                  wired     gen_drv records steady capped cases (ENDLESS) and returns them as endless cases before the long retry
"""
import os
import re
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
GEN = os.path.join(TOOLS, '5-generated', 'gen_equiv')
sys.path[:0] = [GEN, os.path.join(TOOLS, '5-generated'), TOOLS]
import toolpath  # noqa: E402,F401
import sh4sim  # noqa: E402
import directed  # noqa: E402

BASE = 0x8C010000


def main():
    bad = []
    d = tempfile.mkdtemp()
    try:
        poll = [0xE115, 0xD205, 0x6322, 0x3312, 0x8B01, 0xAFFB, 0x0009, 0x000B, 0x0009, 0x0009, 0x0009, 0x0009]
        count = [0xD502, 0x4510, 0x8BFD, 0x000B, 0x0009, 0x0009]
        for name, words, pool, poke, want in (('poll', poll, BASE + 0x100, {'%08X' % (BASE + 0x100): '19000000'}, True),
                                              ('count', count, 0x7FFFFFFF, {}, False)):
            body = b''.join(struct.pack('<H', w) for w in words)
            body += b'\x00\x00' * ((0x18 - len(body) if name == 'poll' else 0x0C - len(body)) // 2) + struct.pack('<I', pool)
            open(os.path.join(d, name + '.bin'), 'wb').write(body + b'\x00' * (0x200 - len(body)))
            r = sh4sim.run({'poke': poke, 'exe': name + '.bin', 'base': '%08X' % BASE, 'entry': '%08X' % BASE,
                            'end': '%08X' % (BASE + 0x12), 'steps': 20000, 'trace': True}, d)
            try:
                got = directed.steady_state(r.get('trace') or [])
            except AttributeError:
                sys.exit('[ERROR] steady check failed:\ndirected.py has no steady_state()')
            if not str(r['error']).startswith('more than'):
                bad.append('%s: the run did not hit the step limit (%s): the test does not show it' % (name, r['error']))
            if got != want:
                bad.append('%s: steady %s, want %s' % (name, got, want))
    finally:
        shutil.rmtree(d, ignore_errors=True)
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(TOOLS, os.path.join(tmp, 'tools'), ignore=shutil.ignore_patterns('__pycache__'))
        script = ("import sys; sys.path.insert(0, 'tools'); import toolpath, equiv\n"
                  "o = {'calls': [1, 2, 3, 4], 'devices': [['r', 'A', 4, '0']] * 5, 'writes': [1], 'error': 'more than 20000'}\n"
                  "m = {'calls': [1, 2, 3], 'devices': [['r', 'A', 4, '0']] * 3, 'writes': [2], 'error': 'more than 20000'}\n"
                  "a, b = equiv.cut_endless(o, m)\n"
                  "print('cut', len(a['calls']), len(b['calls']), len(a['devices']), len(b['devices']), a['error'], b['error'])\n")
        import subprocess
        out = subprocess.run([sys.executable, '-c', script], cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             universal_newlines=True).stdout.strip().split('\n')[-1]
        if out != 'cut 3 3 3 3 None None':
            bad.append('cut: %s' % out[-200:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    drv = open(os.path.join(GEN, 'gen_drv.py')).read()
    fn = re.search(r'^def declared_endless\(.*?(?=^\S)', drv + '\nX', re.M | re.S)
    if not fn:
        bad.append('declared: gen_drv has no declared_endless()')
    else:
        ns = {'os': os}
        exec(fn.group(0), ns)
        tmp2 = tempfile.mkdtemp()
        here = os.getcwd()
        try:
            os.chdir(tmp2)
            none = ns['declared_endless']('main')
            open('endless.txt', 'w').write('# the game loops\nmain   # frame counter only\n\nloopfn\n')
            got = (ns['declared_endless']('main'), ns['declared_endless']('loopfn'), ns['declared_endless']('other'))
        finally:
            os.chdir(here)
            shutil.rmtree(tmp2, ignore_errors=True)
        if none or got != (True, True, False):
            bad.append('declared: no file %s, listed %s' % (none, got))
    if drv.count('declared_endless(name)') < 2:
        bad.append('declared: drawing does not use declared_endless in both the case run and the probe')
    body = re.search(r'^def tests\(.*?(?=^def |\Z)', drv, re.M | re.S)
    text = body.group(0) if body else ''
    if 'ENDLESS' not in drv or 'steady_state' not in drv:
        bad.append('wired: gen_drv does not record steady capped cases')
    elif not re.search(r'ENDLESS.*?STEPS\[0\]=LONG_STEPS', text, re.S):
        bad.append('wired: the endless fallback does not come before the long-cap retry')
    mend = re.search(r'^def mend\(.*?(?=^def |\Z)', drv, re.M | re.S)
    if not mend or 'ENDLESS' not in mend.group(0) or 'declared_endless' not in mend.group(0):
        bad.append('wired: mend still repairs a function whose cases are steady and past repair')
    if not mend or 'MENDT' not in mend.group(0):
        bad.append('wired: repair has no time budget per function')
    if 'steps=20000,trace=True' not in drv:
        bad.append('wired: no cheap 20,000-step probe once a function has been steady on two cases')
    if bad:
        sys.exit('[ERROR] steady check failed:\n' + '\n'.join(bad))
    print('[steady] ok: a run that has stopped changing is told from a long count, and drawing uses it before the long retry')


if __name__ == '__main__':
    main()
