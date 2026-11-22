#!/usr/bin/env python3
"""Hardware a host does not have gets a stub in the port build, by sdk.txt's `hardware` lines (scripts/tools/10-port/native_build.py).
No game data, no compiler. Stdlib only.

    stub      of the functions with no C, one inside a `hardware` range gets a stub that reports itself; the others are run
              from the original code. The ranges decide it, not a list of names: `kdSomethingElse`, outside every range, is
              run although its name looks like the Maple driver's
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(os.path.dirname(HERE), 'scripts', 'tools')


class HardwareStub(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='hardware_stub')
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for d in ('src', os.path.join('port', 'runtime'), 'tools'):
            os.makedirs(os.path.join(self.tmp, d))
        with open(os.path.join(self.tmp, 'src', 'a.c'), 'w') as fp:
            fp.write('int f(void) { return 0; }\n')
        with open(os.path.join(self.tmp, 'sdk.txt'), 'w') as fp:
            fp.write('range 0c14ab88 0c1789b0 SDK libraries\nhardware 0c15fc8e 0c1605ca GD-ROM file system\n')
        shutil.copy(os.path.join(TOOLS, 'toolpath.py'), os.path.join(self.tmp, 'tools'))
        os.makedirs(os.path.join(self.tmp, 'tools', 'common'), exist_ok=True)
        shutil.copy(os.path.join(TOOLS, 'common', 'layout.py'), os.path.join(self.tmp, 'tools', 'common'))
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
        spec = importlib.util.spec_from_file_location('native_build_hardware_stub',
                                                      os.path.join(self.tmp, 'tools', '10-port', 'native_build.py'))
        self.nb = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.nb)

    def test_stub(self):
        fns = {'gdFsRead': 0x0C160116, 'syRtcGet': 0x0C170000, 'kdSomethingElse': 0x0C171000}
        self.assertEqual(self.nb.interpreted(['gdFsRead', 'kdSomethingElse', 'syRtcGet'], fns, self.tmp),
                         ['kdSomethingElse', 'syRtcGet'])


if __name__ == '__main__':
    unittest.main()
