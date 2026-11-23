"""The generator's last passes on a function's C (scripts/tools/5-generated/gen_equiv/rewrites.py last_passes, called by gen_drv.build
after the C is written): every size rewrite the generator can apply to its own output, in one place, each behind its GEN_<NAME>
switch (0 turns it off). New C is born with them, so shrink.py --passes finds less to do. No game data, no compiler. Stdlib only.

    last_passes   smod       the sign sequence of a signed remainder by a power of two comes out as `% 0x40` (GEN_SMOD=0 leaves it)
                  selfcopy   a frame slot stored back with its own value goes (GEN_SELFCOPY=0 leaves it)
                  struct     a far field access is a member of a one-field structure (GEN_STRUCT=0 leaves it)
                  order      the passes run in the order shrink.py's default --passes list names them, each on what the one before
                             gave: smod before switch and copies, rebase last
                  wired      gen_drv.build calls last_passes and no longer lists the passes itself
"""
import os
import re
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
TOOLS = os.path.join(SKILL, 'scripts', 'tools')

SMOD = """int f(int a4)
{
    register int t5;
    t5 = nlRand();
    if ((int)t5 >= 0) {
        t5 = (t5 & 0x3F);
    } else {
        t5 = (~t5);
        t5 = (t5 + 0x1);
        t5 = (t5 & 0x3F);
        t5 = (~t5);
        t5 = (t5 + 0x1);
    }
    return t5;
}
"""

SELF = """int f(int a4)
{
    int stk[8];
    *(unsigned int *)(((int)stk + 12)) = *(int *)((int)stk + 12);
    return a4;
}
"""

STRUCT = """int f(int a4)
{
    *(unsigned int *)((a4 + 0x2D4)) = 0x1;
    return a4;
}
"""


class TestLastPasses(unittest.TestCase):
    def setUp(self):
        saved = list(sys.path)
        self.addCleanup(sys.path.__setitem__, slice(None), saved)
        sys.path.insert(0, os.path.join(TOOLS, '5-generated', 'gen_equiv'))
        sys.path.insert(0, TOOLS)
        import toolpath  # noqa: F401
        import rewrites
        self.rw = rewrites
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        for k in [k for k in os.environ if k.startswith('GEN_')]:
            del os.environ[k]

    def test_smod(self):
        got = self.rw.last_passes(SMOD)
        self.assertIn('t5 = (t5 % 0x40);', got)
        self.assertNotIn('~', got)

    def test_smod_off(self):
        os.environ['GEN_SMOD'] = '0'
        self.assertEqual(self.rw.last_passes(SMOD), SMOD)

    def test_selfcopy(self):
        self.assertNotIn('stk + 12', self.rw.last_passes(SELF))

    def test_selfcopy_off(self):
        os.environ['GEN_SELFCOPY'] = '0'
        os.environ['GEN_REBASE'] = '0'      # rebase would move the offsets it is looking for
        self.assertIn('stk + 12', self.rw.last_passes(SELF))

    def test_struct(self):
        self.assertIn('struct o2D4_uint', self.rw.last_passes(STRUCT))

    def test_struct_off(self):
        os.environ['GEN_STRUCT'] = '0'
        self.assertNotIn('struct o2D4', self.rw.last_passes(STRUCT))

    def test_order_follows_shrink(self):
        order = self.rw.LAST_PASSES
        names = [n for n, _, _ in order]
        self.assertEqual(names[-1], 'rebase')
        self.assertLess(names.index('smod'), names.index('switch'))
        self.assertLess(names.index('smod'), names.index('copies'))
        src = open(os.path.join(TOOLS, '7-reduction', 'shrink.py')).read()
        listed = re.search(r"PASSES = \[([^\]]*)\]", src).group(1)
        shrink = [x.strip().strip("'") for x in listed.split(',')]
        for n in names:
            self.assertIn(n, shrink + ['voidret'], n)

    def test_wired(self):
        src = open(os.path.join(TOOLS, '5-generated', 'gen_equiv', 'gen_drv.py')).read()
        self.assertIn('rewrites.last_passes(', src)
        self.assertNotIn("os.environ.get('GEN_SELFCOPY'", src)


if __name__ == '__main__':
    unittest.main()
