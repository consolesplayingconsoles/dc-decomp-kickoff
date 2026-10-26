#!/usr/bin/env python3
"""The proof cache across a checker change (scripts/tools/equiv.py proof_keys) in a scratch folder, no game data. Stdlib only.

    check.py      a pass stored with the checker as it was, then the checker changes:
                    frozen    with the old equiv.py and sh4sim.py in state/proof-key-frozen/, the old key is one of the keys looked up
                    without   without them, it is not (the change voids the pass)
                    stored    a new pass is stored under the key of the checker as it is now
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools')
sys.path.insert(0, TOOLS)
import toolpath  # noqa: E402,F401
import equiv  # noqa: E402
import sh4sim  # noqa: E402


def main():
    bad = []
    d = tempfile.mkdtemp()
    os.chdir(d)
    open('cases.json', 'w').write('{"dev": []}')
    old_e, old_s = os.path.join(d, 'old_equiv.py'), os.path.join(d, 'old_sh4sim.py')
    open(old_e, 'w').write('# the checker before the change\n')
    open(old_s, 'w').write('# the simulator before the change\n')
    args = (b'code', 0, 'cases.json', {'dev': []}, b'orig', ('ret',))
    old_key = equiv.proof_key(*args, srcs=(old_e, old_s))
    keys = equiv.proof_keys(*args)
    if old_key in keys:
        bad.append('without: a pass under another checker is found with no frozen copy')
    os.makedirs(os.path.join('state', 'proof-key-frozen'))
    for src, name in ((old_e, 'equiv.py'), (old_s, 'sh4sim.py')):
        open(os.path.join('state', 'proof-key-frozen', name), 'w').write(open(src).read())
    keys = equiv.proof_keys(*args)
    if old_key not in keys:
        bad.append('frozen: the pass stored with the frozen checker is not looked up')
    if keys[0] != equiv.proof_key(*args):
        bad.append('stored: a new pass is not stored under the current checker')
    if bad:
        sys.exit('[ERROR] proofkey check failed:\n' + '\n'.join(bad))
    print('[proofkey] ok: passes stored with the frozen checker still count; new ones are stored with the current one')


if __name__ == '__main__':
    main()
