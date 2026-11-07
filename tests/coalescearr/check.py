#!/usr/bin/env python3
"""coalesce.py never gives a temporary the name of an array local (scripts/tools/5-generated/gen_equiv/coalesce.py). Stdlib only.

It named the shared variables t0, t1, ... u0, u1, ... from the pool size, and the generator's ftrv vectors are float arrays named u<N> too:
a scalar renamed to the name of an array was declared twice and the compiler stopped (Zombie Revenge FUN_0c0ed6d8, `float u3[4];` and
`register float u3;`, "Not a parameter name").

    check.py      two float temporaries that can share a name, and an array u0:
                    apart     the shared name is not u0, the name the array has
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '5-generated', 'gen_equiv'))
import coalesce  # noqa: E402

TEXT = '''float f(float a4)
{
    float u1;
    float u2;
    float u0[4];

    u1 = a4 * 2.0f;
    u0[0] = u1;
    u2 = u0[0] + 1.0f;
    return u2;
}'''


def main():
    out = coalesce.coalesce(TEXT)
    scalars = re.findall(r'^\s+float (u\d+);', out, re.M)
    arrays = re.findall(r'^\s+float (u\d+)\[', out, re.M)
    bad = []
    if 'u0' in scalars and 'u0' in arrays:
        bad.append('apart: u0 is declared as a scalar and as an array:\n%s' % out)
    if len(set(scalars)) != len(scalars) or set(scalars) & set(arrays):
        bad.append('apart: a name is declared twice:\n%s' % out)
    if bad:
        sys.exit('[ERROR] coalescearr check failed:\n' + '\n'.join(bad))
    print('[coalescearr] ok: a shared temporary never takes the name of an array')


if __name__ == '__main__':
    main()
