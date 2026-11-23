"""The generator's size gate on `frame` (scripts/tools/5-generated/gen_equiv/framegate.py, called by gen_drv.build when GEN_FRAME=gate).
frame.scalarize (frame slots read and written as one scalar become locals) was the biggest kept gain of the Power Stone 2 shrink
batches, 5,076 of 6,598 bytes over 138 units, but it can make a function much bigger (4,784 to 10,064), so it cannot simply be on:
the generator builds the function with and without it, compiles both and keeps the smaller. No game data, no compiler: build and size
are stand-ins. Stdlib only.

    build_gated   smaller    the framed C is smaller: it is returned
                  bigger     the framed C is bigger: the plain C is returned
                  tie        equal sizes: the plain C (no change for nothing)
                  plain none the plain C does not compile and the framed does: the framed C
                  framed none the framed C does not compile: the plain C
                  both none  neither measurable: the plain C
                  env        GEN_FRAME is 0 while the plain C is built, 1 for the framed one, and back to what it was after
                  off        GEN_FRAME unset, 0 or 1: one build, no sizes asked (1 builds the framed C, as it always did)
                  fails      the framed build raises: the plain C
                  wired      gen_drv.build is the gate around gen_drv._build
"""
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'scripts', 'tools', '5-generated', 'gen_equiv'))
import framegate  # noqa: E402


class TestFrameGate(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop('GEN_FRAME', None)
        self.built = []
        self.sized = []

    def build(self, name, ret, passthru=False):
        self.built.append(os.environ.get('GEN_FRAME'))
        if os.environ.get('GEN_FRAME') == '1' and self.framed_raises:
            raise RuntimeError('frame')
        return ('framed' if os.environ.get('GEN_FRAME') == '1' else 'plain', 'c-' + os.environ.get('GEN_FRAME', '?'))

    framed_raises = False

    def run_gate(self, plain, framed, mode='gate'):
        os.environ['GEN_FRAME'] = mode
        sizes = {'plain': plain, 'framed': framed}

        def size(name, text, c):
            self.sized.append(text)
            return sizes[text]
        return framegate.build_gated(self.build, size, 'f', 'r0', False)

    def test_smaller(self):
        self.assertEqual(self.run_gate(100, 80)[0], 'framed')

    def test_bigger(self):
        self.assertEqual(self.run_gate(100, 140)[0], 'plain')

    def test_tie(self):
        self.assertEqual(self.run_gate(100, 100)[0], 'plain')

    def test_plain_none(self):
        self.assertEqual(self.run_gate(None, 90)[0], 'framed')

    def test_framed_none(self):
        self.assertEqual(self.run_gate(100, None)[0], 'plain')

    def test_both_none(self):
        self.assertEqual(self.run_gate(None, None)[0], 'plain')

    def test_env(self):
        self.run_gate(100, 80)
        self.assertEqual(self.built, ['0', '1'])
        self.assertEqual(os.environ['GEN_FRAME'], 'gate')

    def test_off(self):
        for mode, want in (('0', ['0']), ('1', ['1'])):
            self.built.clear()
            self.sized.clear()
            got = self.run_gate(100, 80, mode)
            self.assertEqual(self.built, want, mode)
            self.assertEqual(self.sized, [], mode)
        os.environ.pop('GEN_FRAME')
        self.built.clear()
        framegate.build_gated(self.build, lambda *a: 1 / 0, 'f', 'r0', False)
        self.assertEqual(len(self.built), 1)

    def test_fails(self):
        self.framed_raises = True
        self.assertEqual(self.run_gate(100, 80)[0], 'plain')

    def test_wired(self):
        src = open(os.path.join(HERE, '..', 'scripts', 'tools', '5-generated', 'gen_equiv', 'gen_drv.py')).read()
        self.assertIn('def _build(name,ret,passthru=False):', src)
        self.assertIn('framegate.build_gated(_build,', src)


if __name__ == '__main__':
    unittest.main()
