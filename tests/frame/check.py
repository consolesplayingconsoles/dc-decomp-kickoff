#!/usr/bin/env python3
"""frame.scalarize turns a frame slot that is only ever read and written as one scalar into a local (Virtua Tennis cpuSglAimTable reloaded
`a4` from `stk + 32` 373 times; SHC cannot keep a value that lives in an array in a register). A slot a struct access, an address or an index
reaches, one used as two sizes, and one used once stay in the frame. A new local starts with the slot's contents, loaded at the top.
No game data, no compiler. Stdlib only.

    check.py      small functions through scalarize:
                    int       int and unsigned int accesses at one offset become R<1000+offset>, loaded once at the top
                    sum       an access written as `(0xBC + ((int)stk + 52)) + 0x0` is the slot at 240
                    float     a float-only slot is a float local
                    stuck     a struct access over the slot, an address taken, a variable index `stk[a4]`, a variable added to the frame address, a slot used as
                              int and float, and a slot used once keep their frame accesses
                    twice     a second pass changes nothing
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '5-generated', 'gen_equiv'))
import frame  # noqa: E402


def fn(*body):
    return '\n'.join(['int f(int a4)', '{', '    int t1;', '    int stk[69];', ''] + ['    ' + b for b in body] + ['}'])


def main():
    bad = []
    t = fn('*(int *)((int)stk + 32) = a4;', 't1 = *(int *)(((int)stk + 32));', '*(unsigned int *)((int)stk + 32) = (t1 + 1);', 'return t1;')
    o = frame.scalarize(t)
    if 'R1032' not in o or o.count('(int)stk + 32') != 1 or '    int R1032;' not in o or 'R1032 = *(int *)((int)stk + 32);' not in o:
        bad.append('int: %s' % o)
    t = fn('*(float *)(((0xBC + ((int)stk + 52)) + 0x0)) = 1.0f;', 'g(*(float *)(((0xBC + ((int)stk + 52)) + 0x0)));')
    o = frame.scalarize(t)
    if '    float R1240;' not in o or 'R1240 = *(float *)((int)stk + 240);' not in o:
        bad.append('sum/float: %s' % o)
    o = frame.scalarize(fn('stk[11] = a4;', 't1 = *(int *)((int)stk + 44);', 'return t1;'))
    if 'R1044 = a4;' not in o or 't1 = R1044;' not in o:
        bad.append('index: a constant stk[11] is the int slot at 44: %s' % o)
    o = frame.scalarize(fn('*(int *)((int)stk + 32) = a4;', 't1 = *(int *)((0xB5C + (*(int *)(((int)stk + 32)))));', 'return t1;'))
    if 'R1032 = a4;' not in o or '*(int *)((0xB5C + (R1032)));' not in o:
        bad.append('through: a field read through a pointer kept in a slot: %s' % o)
    cases = {
        'struct over the slot': fn('*(int *)((int)stk + 44) = a4;', 't1 = *(int *)((int)stk + 44);', 'g(*(Stk3 *)(((int)stk + 40)));'),
        'address taken': fn('*(int *)((int)stk + 44) = a4;', 't1 = *(int *)((int)stk + 44);', 'g((int)stk + 44);'),
        'indexed by a variable': fn('*(int *)((int)stk + 44) = a4;', 't1 = *(int *)((int)stk + 44);', 'stk[a4] = 1;'),
        'variable index': fn('*(int *)((int)stk + 44) = a4;', 't1 = *(int *)((int)stk + 44);', 'g(*(int *)((int)stk + (a4 << 2)));'),
        'int and float': fn('*(int *)((int)stk + 44) = a4;', 'g(*(float *)((int)stk + 44));'),
        'used once': fn('*(int *)((int)stk + 44) = a4;'),
        'short': fn('*(short *)((int)stk + 44) = a4;', 't1 = *(short *)((int)stk + 44);'),
    }
    for k, c in cases.items():
        if frame.scalarize(c) != c:
            bad.append('stuck: %s was changed' % k)
    if frame.scalarize(frame.scalarize(fn('*(int *)((int)stk + 32) = a4;', 't1 = *(int *)(((int)stk + 32));'))) != frame.scalarize(fn('*(int *)((int)stk + 32) = a4;', 't1 = *(int *)(((int)stk + 32));')):
        bad.append('twice: a second pass changes the text')
    if bad:
        sys.exit('[ERROR] frame check failed:\n' + '\n'.join(bad))
    print('[frame] ok: scalar frame slots become locals loaded once; struct, address, index, mixed-type, short and single-use slots stay; idempotent')


if __name__ == '__main__':
    main()
