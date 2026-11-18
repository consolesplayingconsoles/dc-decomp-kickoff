# Working on dc-decomp-kickoff: how it is tested

These rules bind everyone who changes this repo, person or agent.

## The rule

**A change starts with a test.** A bug fix, a new tool, a new rule, a changed format: the unit test that
describes the new behaviour is written first, run, and seen to FAIL on the code as it is. Only then is
the code changed, until the test passes. A test that has never failed proves nothing: it may be testing
nothing.

- Bug fix: the test reproduces the bug with the smallest synthetic input that shows it, and says in its
  docstring what behaviour it protects. It names no game, function or address of a game.
- Evidence is not test text. Which game exposed a bug, what it looked like there and how it was found are
  written in `docs/evidence.md`, in the entry for that technique, never in a test or in this file.
- New behaviour: one test method for each thing it must do, named for that thing.
- A change that cannot be tested (a doc, a comment) needs no test; a change to what a tool prints or
  writes is behaviour, and does.
- Never loosen or delete a test to make a change pass. If a test is wrong, say why in the change and
  fix the test on its own.
- A test that is skipped says why in `self.skipTest(...)`, and the reason is a bug to fix, not a state to keep.

## The standard

The tests follow Python's conventions and nothing of our own:

- `unittest` from the standard library (the tools run on old hardware: **stdlib only**, and the files
  parse as Python 3.6, which the pre-commit hook checks).
- One module for a subject: `tests/test_<subject>.py`, lowercase `snake_case`. The subject is the tool
  or the behaviour it protects (`test_sh4sim`-style names for a tool, `test_fmovpair` for one behaviour).
- A `unittest.TestCase` class per area, a `test_*` method per behaviour, named for the behaviour
  (`test_store_with_pre_decrement`), with `self.assert*` and a message that says what was wanted.
- The module docstring says what is protected and why, in a few lines.
- Run one: `python3 -m unittest tests.test_<subject>`. Run all: `python3 -m unittest discover -s tests`.
- No game data and no compiler in any test. Inputs are built in the test from nothing (a few
  instruction words, a tiny function list, a temp folder with a copy of the tools); they can be
  committed and run anywhere.
- A test leaves nothing behind: temp folders are removed (`tempfile.TemporaryDirectory`), and the
  working directory, `sys.path` and the environment are put back (`setUp` and `addCleanup`).
- A test does not depend on the order it runs in or on another test's output.

## The older tests

The tests written before this standard were moved to it by name and shape (`test_<subject>.py`,
`TestCase`, discovery) and keep the body they had: one method that collects failures in a list and
asserts it empty. When you touch one, rewrite what you touch as one method per behaviour with real
assertions. New tests are written that way from the start.

## Fixtures and the compatibility check

- Data a test reads sits beside it in a folder of its own. `tests/compat/` holds the map readers'
  synthetic inputs (`emit.py`) and their expected output (`golden.json`); the viewer's own check reads
  both, so they stay where they are.
- `tests/test_compat.py` compares what the readers find now with `golden.json`: an existing entry may not
  change or disappear. Accepting new entries, or a deliberate break, is
  `python3 tests/compat/update_golden.py [--breaking vX.Y]`, never an edit of the golden file by hand.
- Shuriken Explorer reads this repo's readers through that check: when a reader changes, its test
  (`bash app/test/run.sh` in its repo) must agree with the skill's.

## Before a change is done

1. The new test failed before the change and passes after it.
2. `python3 -m unittest discover -s tests` passes.
3. The test and the change belong together: one change carries both.
