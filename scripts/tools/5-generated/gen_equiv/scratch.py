"""scratch.py: the scratch C a run writes to src/ and tests/ (src/gen_tmp<round>p<pid>[c|v].c, tests/gen_tmp<round>p<pid>[c|v], and the
recheck's gen_tmpK<pid>) and takes away again.

A function defined in a scratch file counts as defined, so the next run does not pick it, and the build's checks read it: a run that
ended or was stopped without removing its files left functions out of every later run and a void declaration in front of retcheck.
The files are named after the process that wrote them, so a run removes its own (remove_own) and the next run removes those of a
process that is gone (sweep), never those of one still running side by side, and never a file git tracks (scratch that was committed
is the project's C now: a proven function may be defined only there). src/ may have folders of its own; they are searched too.
"""
import glob
import os
import re
import shutil
import subprocess

NAME = re.compile(r'^gen_tmp(?:K(?P<k>\d+)|\d+p(?P<p>\d+))[a-z]*(?:\.c)?$')


def _pid(path):
    m = NAME.match(os.path.basename(path))
    if not m:
        return None
    return int(m.group('k') or m.group('p'))


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _paths(srcdir, testsdir):
    # src/ may hold the C in folders of its own (src/game/..., src/lib/...): the scratch is written next to the batch files
    return glob.glob(os.path.join(srcdir, '**', 'gen_tmp*.c'), recursive=True) + glob.glob(os.path.join(testsdir, '**', 'gen_tmp*'), recursive=True)


def _tracked(paths):
    """the paths git tracks: scratch that was committed is the project's C now (a proven function may live only there), never removed here"""
    if not paths:
        return set()
    try:
        out = subprocess.run(['git', 'ls-files', '-z', '--'] + paths, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout
    except OSError:
        return set()
    names = {os.path.normpath(p) for p in out.decode('utf-8', 'replace').split('\0') if p}
    return {p for p in paths if os.path.normpath(p) in names or any(n.startswith(os.path.normpath(p) + os.sep) for n in names)}


def _remove(path):
    if os.path.isdir(path):
        shutil.rmtree(path, True)
    elif os.path.exists(path):
        os.remove(path)


def sweep(srcdir='src', testsdir='tests'):
    """remove the scratch of processes that no longer run; the removed paths"""
    gone = []
    paths = _paths(srcdir, testsdir)
    keep = _tracked(paths)
    for p in paths:
        pid = _pid(p)
        if pid is not None and not _alive(pid) and p not in keep:
            _remove(p)
            gone.append(p)
    return gone


def remove_own(srcdir='src', testsdir='tests', pid=None):
    """remove this process's scratch, whatever its letter suffix; the removed paths"""
    pid = os.getpid() if pid is None else pid
    gone = []
    for p in _paths(srcdir, testsdir):
        if _pid(p) == pid:
            _remove(p)
            gone.append(p)
    return gone
