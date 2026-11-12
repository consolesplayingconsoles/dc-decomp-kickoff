#!/usr/bin/env python3
"""The generator's retry with one temporary per value (scripts/tools/5-generated/gen_equiv/uncoalesced.py). SHC merged two tails of
Zombie Revenge FUN_0c02ad98 that tested different call results held in one shared temporary, and gave case 2 the condition of case 6;
the same C with a temporary per value compiles right. No game data, no compiler: build and check are stand-ins. Stdlib only.

    check.py      f_merge  differs coalesced, passes uncoalesced:   returned with its new item
                  f_bad    differs both ways:                      not returned
                  f_none   builds nothing:                         not returned
                  GEN_COALESCE is 0 while building and back to its value after (unset, or '1'); with GEN_COALESCE=0 already set,
                  nothing is retried and check is never called
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), 'scripts', 'tools', '5-generated', 'gen_equiv'))
from uncoalesced import retry_uncoalesced  # noqa: E402

seen = []


def build(n):
    seen.append(os.environ.get('GEN_COALESCE'))
    if n == 'f_none':
        return None
    return (n, 'C of %s, coalesce=%s' % (n, os.environ.get('GEN_COALESCE')))


def check(items):
    return [it[0] for it in items if it[0] == 'f_merge' and it[1].endswith('coalesce=0')]


def main():
    for before in (None, '1'):
        if before is None:
            os.environ.pop('GEN_COALESCE', None)
        else:
            os.environ['GEN_COALESCE'] = before
        seen.clear()
        got = retry_uncoalesced(['f_merge', 'f_bad', 'f_none'], build, check)
        assert set(got) == {'f_merge'}, 'wrong functions pass: %s' % sorted(got)
        assert got['f_merge'][1].endswith('coalesce=0'), 'the passing item is not the uncoalesced build'
        assert seen and all(v == '0' for v in seen), 'built while GEN_COALESCE was %s' % seen
        assert os.environ.get('GEN_COALESCE') == before, 'GEN_COALESCE not restored to %r' % before
    os.environ['GEN_COALESCE'] = '0'
    called = []
    got = retry_uncoalesced(['f_merge'], build, lambda items: called.append(1) or [])
    assert got == {} and not called, 'a run already uncoalesced retried'
    print('[gen_uncoalesced] ok: a function that still differs is built again with a temporary per value and kept when it passes')


main()
