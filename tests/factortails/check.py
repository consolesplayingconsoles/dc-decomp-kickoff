#!/usr/bin/env python3
"""A tail the structured form copied into an arm is written once (scripts/tools/5-generated/gen_equiv/gen_drv.py factor_tails).
No game data, no compiler. Stdlib only.

The structured form copies the code after a join into each arm that reaches it: `if (c) { P; T } Q; T` with T ending in a return
(Zombie Revenge FUN_0c02ce56: a ten-line ending three times, 244 bytes in the original, 1,376 in C).

    check.py      factor_tails on C text:
                    once      `if (c) { a = 1; f(); return 2; } b = 3; f(); return 2;` -> `if (c) { a = 1; } else { b = 3; } f(); return 2;`
                    blocks    a tail holding a whole if block is moved too
                    arm       an arm left empty becomes the negated condition around the other code
                    keep      an arm that does not end in a return (it falls through) is left as it is
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(SKILL, 'scripts', 'tools', '5-generated', 'gen_equiv'))


def main():
    os.chdir(os.path.join(SKILL, 'tests', 'factortails'))
    sys.path.insert(0, os.path.join(SKILL, 'scripts', 'tools'))
    import importlib.util
    spec = importlib.util.spec_from_file_location('gd', os.path.join(SKILL, 'scripts', 'tools', '5-generated', 'gen_equiv', 'gen_drv.py'))
    src = open(spec.origin).read()
    ns = {'re': __import__('re')}
    i = src.index('def factor_tails(body):')
    j = src.index('\ndef ', i + 1)
    exec(src[i:j], ns)
    ft = ns['factor_tails']
    bad = []
    got = ft(['if (c) {', '    a = 1;', '    f();', '    return 2;', '}', 'b = 3;', 'f();', 'return 2;'])
    if got != ['if (c) {', '    a = 1;', '} else {', '    b = 3;', '}', 'f();', 'return 2;']:
        bad.append('once: %s' % got)
    got = ft(['if (c) {', '    a = 1;', '    if (d) {', '        e = 2;', '    }', '    return 2;', '}', 'b = 3;', 'if (d) {', '    e = 2;', '}', 'return 2;'])
    if got != ['if (c) {', '    a = 1;', '} else {', '    b = 3;', '}', 'if (d) {', '    e = 2;', '}', 'return 2;']:
        bad.append('blocks: %s' % got)
    got = ft(['if (c) {', '    f();', '    return 2;', '}', 'b = 3;', 'f();', 'return 2;'])
    if got != ['if (!(c)) {', '    b = 3;', '}', 'f();', 'return 2;']:
        bad.append('arm: %s' % got)
    src_ = ['if (c) {', '    a = 1;', '    f();', '}', 'b = 3;', 'f();', 'return 2;']
    got = ft(list(src_))
    if got != src_:
        bad.append('keep: %s' % got)
    if bad:
        sys.exit('[ERROR] factortails check failed:\n' + '\n'.join(bad))
    print('[factortails] ok: a tail copied into an arm is written once')


if __name__ == '__main__':
    main()
