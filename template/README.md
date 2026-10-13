# @TITLE@ decomp (kick-off)

A decompilation of the Dreamcast **@TITLE@**, in progress. It rebuilds the game's executable
byte for byte from one assembly file per function (the baseline the build keeps checking), with
@NAMED@ of its @FUNCS@ functions named so far. A function is **done** when its C behaves like the
original (Equivalent, checked by `tools/equiv.py`); byte-identical C (Matching) is the bonus tier.

**This repository contains no game code or data.** You supply your own disc; `setup.sh` generates
everything game-derived on your machine, and `.gitignore` keeps it out of git.

## Supported version

| | |
|---|---|
| Release | @RELEASE@ |
| `@BOOT@` | @SIZE@ bytes, SHA-1 `@SHA1@` |
| Linked at | `0x@BASE@` |
| SDK era | @SDK@ |

Other releases are different builds: `setup.sh` refuses them rather than produce a broken split.

## Building

You need: your own copy of the disc as a `.gdi` (a `.chd` converts with
`chdman extractcd -i game.chd -o game.gdi`), Python 3, Docker, and a Katana SDK (its Hitachi
assembler and linker do the build; any folder layout works).

```
bash setup.sh "path/to/your disc.gdi"
echo 'SDK_PATH="/path/to/katana-sdk"' > .env      # once: where your SDK is (not committed)
bash build.sh
```

`build.sh` should end with `MATCH`. It builds its own small tools image the first time (Docker
must be running). The first build assembles every file (a few minutes); after
that only changed files. (Running the scripts with `bash` means file permissions never matter;
`./build.sh` works too once `setup.sh` has run.) Docker is required; on Linux x86_64 without
Docker, `DC_LOCAL=1` runs the tools through `wibo` instead.

## What is here

| path | what |
|---|---|
| `functions.txt` | every function: address, size, name (`FUN_<addr>` = not named yet) |
| `src/` | C: Equivalent files (checked by `tools/equiv.py`, not built) and matching C units (built, see below) |
| `tests/` | test cases per function (`tests/<file>/<function>.json`) and `tests/equivalent.txt`, the functions found Equivalent |
| `docs/equivalent.md` | the evidence for each Equivalent function (written by `tools/equiv.py`) |
| `models.txt` | what is known about the game's 3D models: tables whose layout is understood (read by `tools/model_map.py`) |
| `symbols.txt` | addresses the C units use that no file defines yet (RAM, data inside asm) |
| `sdk.txt` | which code is Sega's SDK, not the game (for `tools/progress.py`) |
| `BASE` | link address |
| `setup.sh` | extract + verify your executable, generate `asm/`, `text-map/` and `model-map/` |
| `build.sh` | assemble, link, convert, compare with your original |
| `disc.sh` | build a playable disc image of your version (files you put under `disc/`) |
| `textures.sh` | optional: every standard texture on one page, to find text drawn into images |
| `tools/` | disc reader, splitter, text mapper, model mapper, C-unit layout, progress report, missed-function finder, SH-4 disassembler and simulator, the Equivalent check (`equiv.py`) with its helpers (`checksizes.py`, `classify.py`, `poollist.py`, `port_equiv.py`), live checks against the running game (optional) |
| `AGENTS.md` | the per-function decompilation loop: Equivalent first, Matching as the bonus |

`text-map/` (generated) lists the executable's strings with every pointer to them, the text density
of each disc file with the code that opens it, how text is drawn, and image files that probably
hold text (candidates). These are heuristics for you to check, not a verdict.

`model-map/game.dcgs` (generated and committed: addresses, offsets, sizes and names only, no game bytes or text; `setup.sh` rebuilds it) lists every 3D model in the disc files with the name the executable's tables give it
(`models.txt` holds the tables whose layout is known; the rest are named by table address and the functions that use
it), the characters' skeletons placed on their parts, and the texture lists. It is plain tab-separated text in
sections: a model viewer or a spreadsheet can read it.

## Equivalent C and shared library code

`src/<file>.c` with no `@unit` header is C checked for behaviour only: `python3 tools/equiv.py src/<file>.c`
runs each function in an SH-4 interpreter twice per test case, the original bytes and your compiled C,
and they must agree on calls, memory writes and the result. Passing functions are listed in
`tests/equivalent.txt` and counted as done. The loop, and how to write many of them quickly, is in
`AGENTS.md` and the kickoff skill's `references/equivalent-pipeline.md`. Library code the game shares
with another decomp of this skill (the NAOMI library, the C runtime) need not be rewritten:
`python3 tools/port_equiv.py <that decomp> .` finds those functions here by their code, ports the C and
its cases, and keeps only what `equiv.py` confirms on this game's own bytes.

## Matching C units (the build tier)

A file `src/<name>.c` whose first line is `/* @unit <start>-<end> [shc options] */` replaces every
asm file in that address range. `build.sh` compiles it with the SDK's `shc` to assembly, lays it
out exactly like the original (`tools/fill.py`: alignment as nops, reserved gaps as `0xEE`, padded
to `<end>`), assembles it and links it in place; the result still has to `MATCH`. A unit with
constant data (initialised local arrays, const tables, string literals) also names where the
original link put that data: `/* @unit <start>-<end> @data <dstart>-<dend> [shc options] */`. The
data becomes its own piece at that range, in source order; both ranges must start and end on asm
file boundaries (add them to `functions.txt`: `F <addr> 0 FUN_<addr>` for a function start,
`D <addr> 0 data_<addr>` for a data boundary, which is not counted as a function). A unit is one
original source file: all its functions share literal pools, so it goes in only when all of it
matches. `python3 tools/progress.py` reports the state game code and SDK apart (`sdk.txt` marks the SDK),
each game function in one bucket: done (equivalent C, matching C part of it), named only (a name is
not done work), unnamed; plus documented functions and named globals. `docs/equivalent.md` holds
the evidence for each equivalent function.

## Progress

<!-- progress -->
@PROGRESS@
<!-- /progress -->

Updated on every commit by `tools/hooks/pre-commit` (enable once per clone:
`git config core.hooksPath tools/hooks`).

## Names

Names come from signature matching: @NAMED_SDK@ matches from the Katana SDK's own libraries (only
unique matches are applied). @NAMED@
functions carry a name in all, because small wrappers inherit the name of the function they call.

## How this was started

This repo was autogenerated using
[dc-decomp-kickoff](https://github.com/consolesplayingconsoles/dc-decomp-kickoff) @SKILL_VERSION@.

## Third-party sources

The build needs a Katana SDK. Repositories that hold such material (for example
`Kochise/dreamcast-docs`)
are named solely as examples of the type of material required. We have no affiliation with, and
make no representation regarding, those repositories, their contents, or their licensing. You are
solely responsible for determining whether you are entitled to obtain and use any such material.

@TITLE@ and its publisher's trademarks belong to their owners. This project is not affiliated with
or endorsed by them.
