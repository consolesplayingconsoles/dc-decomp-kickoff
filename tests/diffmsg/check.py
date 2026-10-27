#!/usr/bin/env python3
"""The checker's message for a difference names what differs (scripts/tools/equiv.py same). No game data, no compiler. Stdlib only.

    check.py      two runs whose call lists differ at call 25 of 30:
                    names     the message says `calls: call 25/30` and shows that call of each side whole: each list was cut at 200
                              characters, before the call that differed (Virtua Tennis cpuChasePlan: "calls: original [[...], [..."
                              with the difference past the cut)
                    kind      the kind still comes first (`calls:`), and a return value difference still reads `out: original`: step 5
                              finds a difference in the return value alone by that text
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401
import equiv  # noqa: E402


def run(k):
    calls = [{'to': '0C0807B4', 'r4-r7': ['%08X' % i, '00000002', '00000003', '00000004'], 'fr4-fr11': []} for i in range(30)]
    calls[24] = dict(calls[24], **{'r4-r7': ['%08X' % k, '00000002', '00000003', '00000004']})
    return {'error': None, 'out': {'r0': '00000000'}, 'calls': calls, 'writes': [], 'devices': [], 'sr': None}


def main():
    bad = []
    ok, why = equiv.same(run(24), run(99), ['r0'], {})
    if ok or not why.startswith('calls: call 25/30') or '"00000018"' not in why or '"00000063"' not in why:
        bad.append('names: %r' % why[:300])
    a = dict(run(1), out={'r0': '00000001'}); b = dict(run(1), out={'r0': '00000002'})
    ok, why = equiv.same(a, b, ['r0'], {})
    if not why.startswith('out: original'):
        bad.append('kind: a return value difference reads %r' % why[:120])
    if bad:
        sys.exit('[ERROR] diffmsg check failed:\n' + '\n'.join(bad))
    print('[diffmsg] ok: a difference in a list names its first differing entry, whole')


if __name__ == '__main__':
    main()
