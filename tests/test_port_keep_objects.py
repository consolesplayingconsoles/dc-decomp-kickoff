#!/usr/bin/env python3
"""--keep-objects: the port build does not recompile a file only because its own scripts changed (scripts/tools/10-port/native_build.py).
No game data, no compiler. Stdlib only.

    default   a compiled file older than the build's scripts is compiled again: a change to them may change what any file
              compiles to
    keep      with --keep-objects it is kept: for a change that alters only a few files, whose objects are removed or built
              first with --only. A full build took 45 minutes for a change that touched three files of 1,588
    source    a file whose source or prelude is newer than its object is compiled again either way
    missing   a file with no object is compiled either way
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')


class KeepObjects(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='keep_objects')
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for d in ('src', os.path.join('port', 'runtime'), 'tools'):
            os.makedirs(os.path.join(self.tmp, d))
        with open(os.path.join(self.tmp, 'src', 'a.c'), 'w') as fp:
            fp.write('int f(void) { return 0; }\n')
        with open(os.path.join(self.tmp, 'sdk.txt'), 'w') as fp:
            fp.write('range 0c14ab88 0c1789b0 SDK libraries\nhardware 0c15fc8e 0c1605ca GD-ROM file system\n')
        shutil.copy(os.path.join(TOOLS, 'toolpath.py'), os.path.join(self.tmp, 'tools'))
        shutil.copy(os.path.join(TOOLS, 'layout.py'), os.path.join(self.tmp, 'tools'))
        os.makedirs(os.path.join(self.tmp, 'tools', '5-generated'))
        shutil.copy(os.path.join(TOOLS, '5-generated', 'sdk_place.py'), os.path.join(self.tmp, 'tools', '5-generated'))   # the function reader
        shutil.copytree(os.path.join(TOOLS, '10-port'), os.path.join(self.tmp, 'tools', '10-port'),
                        ignore=shutil.ignore_patterns('__pycache__'))
        saved_path, saved_env = list(sys.path), dict(os.environ)
        saved = {k: sys.modules.get(k) for k in ('sh4abi', 'toolpath', 'forwarded', 'frame_reads', 'layout', 'sdk_place')}

        def restore():
            sys.path[:] = saved_path
            os.environ.clear()
            os.environ.update(saved_env)
            for k, v in saved.items():
                sys.modules.pop(k, None)
                if v is not None:
                    sys.modules[k] = v
        self.addCleanup(restore)
        for k in saved:
            sys.modules.pop(k, None)
        spec = importlib.util.spec_from_file_location('native_build_keep_objects',
                                                      os.path.join(self.tmp, 'tools', '10-port', 'native_build.py'))
        self.nb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.nb)

    def test_default(self):
        self.assertTrue(self.nb.needs_compile(100, [50, 60], [150], False))

    def test_keep(self):
        self.assertFalse(self.nb.needs_compile(100, [50, 60], [150], True))

    def test_source(self):
        self.assertTrue(self.nb.needs_compile(100, [120, 60], [10], True))
        self.assertTrue(self.nb.needs_compile(100, [50, 130], [10], False))
        self.assertFalse(self.nb.needs_compile(100, [50, 60], [10], False))

    def test_missing(self):
        self.assertTrue(self.nb.needs_compile(None, [50], [10], True))


    def test_arglist(self):
        """arglist: the game's own vsprintf is the one its calls reach. For a name the host's C library also has (memcpy,
        strlen) the game's calls go to the host's; a function that takes an argument list cannot: the SH-4's list is a plain
        pointer to the values, the host's is a structure, and the host's vsprintf read address 0 (Crazy Taxi, nlPrintf at
        start-up). The game's C for it reads the game's kind of list"""
        names = self.nb.host_names({'memcpy', 'strlen', 'vsprintf', 'vsnprintf', 'vprintf', 'printf'})
        self.assertIn('memcpy', names)
        self.assertIn('printf', names)
        for n in ('vsprintf', 'vsnprintf', 'vprintf'):
            self.assertNotIn(n, names)


if __name__ == '__main__':
    unittest.main()
