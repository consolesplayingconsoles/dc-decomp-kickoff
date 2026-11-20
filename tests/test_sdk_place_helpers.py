#!/usr/bin/env python3
"""A file split by library keeps each part whole: the helpers a part's functions use go with it
(scripts/tools/5-generated/sdk_place.py). No game data, no compiler. Stdlib only.

    helper     a function the file defines that functions.txt does not list (a static helper) is carried into the part
               whose function calls it: split without it, the part did not link (Crazy Taxi: 13 parts, `iaFscaS`)
    both       a helper two parts use is in both
    unused     a part that does not use a helper does not get it
    pragma     `#pragma inline_asm(name)` stays only where `name` is defined: left in a part without the function, the
               compiler stopped on it
    game       the game's part keeps the helpers it uses, and the pragma for them
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(os.path.dirname(HERE), 'scripts', 'tools', '5-generated', 'sdk_place.py')

FUNCS = ('F 0c020100 20 gameThing\nF 0c073a00 16 nlSin\nF 0c073a20 16 nlCos\nF 0c073a40 16 nlPlain\n'
         'F 0c14ac00 16 kmSetThing\n')
SDK = 'range 0c0739c0 0c089f26 NAOMI library\nrange 0c14ab88 0c1789b0 SDK libraries\n'
SRC = '''#pragma inline_asm(iaFscaS)
#pragma inline_asm(iaOcbwb)
int nlSin(int a4);

static int iaFscaS(int a)
{
    FSCA FPUL,DR0
}

static int iaOcbwb(int a)
{
    OCBWB @R4
}

static int scale(int a)
{
    return a * 2;
}

int gameThing(int a4)
{
    return scale(a4) + iaOcbwb(a4);
}

int nlSin(int a4)
{
    return iaFscaS(a4);
}

int nlCos(int a4)
{
    return iaFscaS(a4) + scale(a4);
}

int nlPlain(int a4)
{
    return a4;
}

int kmSetThing(int a4)
{
    return scale(a4);
}
'''


def put(path, text):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w') as fp:
        fp.write(text)


def get(path):
    with open(path) as fp:
        return fp.read()


class SdkPlaceHelpers(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix='sdk_place_helpers')
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.repo)
        put('functions.txt', FUNCS)
        put('sdk.txt', SDK)
        put('layout.txt', 'game 0C020080 0C14AB88\nkeep 0C0739C0 0C14AB88\n')
        put('src/gen_a.c', SRC)
        r = subprocess.run([sys.executable, TOOL, '--fix'], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.naomi, self.kamui, self.game = get('sdk/naomi/gen_a_naomi.c'), get('sdk/kamui/gen_a_kamui.c'), get('src/gen_a.c')

    def test_helper(self):
        self.assertIn('static int iaFscaS(int a)\n{\n    FSCA FPUL,DR0\n}', self.naomi)

    def test_both(self):
        self.assertEqual(self.naomi.count('static int scale(int a)\n{'), 1)
        self.assertEqual(self.kamui.count('static int scale(int a)\n{'), 1)
        self.assertEqual(self.game.count('static int scale(int a)\n{'), 1)

    def test_unused(self):
        self.assertNotIn('iaFscaS(int a)\n{', self.kamui)
        self.assertNotIn('iaOcbwb(int a)\n{', self.naomi)

    def test_pragma(self):
        self.assertIn('#pragma inline_asm(iaFscaS)', self.naomi)
        self.assertNotIn('#pragma inline_asm(iaOcbwb)', self.naomi)
        self.assertNotIn('#pragma inline_asm', self.kamui)

    def test_game(self):
        self.assertIn('static int iaOcbwb(int a)\n{', self.game)
        self.assertIn('#pragma inline_asm(iaOcbwb)', self.game)
        self.assertNotIn('#pragma inline_asm(iaFscaS)', self.game)
        self.assertNotIn('iaFscaS(int a)\n{', self.game)



class SdkPlaceTaken(unittest.TestCase):
    """taken: a part's name that a file already has (`gen_a_naomi`, from an earlier split of a file of that name) gets the next
    free one, `gen_a_naomi_2`; the tool stopped there, with the files before it already moved"""

    def test_taken(self):
        repo = tempfile.mkdtemp(prefix='sdk_place_taken')
        self.addCleanup(shutil.rmtree, repo, True)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(repo)
        put('functions.txt', FUNCS)
        put('sdk.txt', SDK)
        put('layout.txt', 'game 0C020080 0C14AB88\nkeep 0C0739C0 0C14AB88\n')
        put('src/gen_a.c', SRC)
        put('sdk/naomi/gen_a_naomi.c', 'int nlOther(int a4)\n{\n    return a4;\n}\n')
        r = subprocess.run([sys.executable, TOOL, '--fix'], cwd=repo, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('int nlOther(int a4)', get('sdk/naomi/gen_a_naomi.c'))
        self.assertIn('int nlSin(int a4)\n{', get('sdk/naomi/gen_a_naomi_2.c'))
        self.assertTrue(os.path.exists('sdk/kamui/gen_a_kamui.c'))


if __name__ == '__main__':
    unittest.main()
