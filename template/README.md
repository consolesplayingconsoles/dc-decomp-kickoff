# @TITLE@ decomp (kick-off)

![decomp progress](badge.svg)

**Explore this decomp project with [Shuriken Explorer](https://consolesplayingconsoles.github.io/dc-shuriken-explorer/) and see the game's models, skeletons, animations, textures, images, sounds, text and side-by-side C and assembly code directly in your browser.**

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

You need: your own copy of the disc as a `.gdi` with its track files, Python 3, Docker, and a Katana SDK (its Hitachi
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
| `setup.sh` | Extract and verify your executable, generate `asm/`, `text-map/` and `model-map/` |
| `build.sh` | Assemble, link, convert, compare with your original |
| `disc.sh` | Build a playable disc image of your version (files you put under `disc/`) |
| `textures.sh` | Optional: every standard texture on one page, to look through |
| `BASE` | Link address |
| `functions.txt` | Every function: address, size, name (`FUN_<addr>` = not named yet) |
| `symbols.txt` | Addresses the C units use that no file defines yet (RAM, data inside asm) |
| `sdk.txt` | The bundled Sega SDK's code (for `tools/progress.py`) |
| `models.txt` | What is known about the game's 3D models: tables whose layout is understood (read by `tools/model_map.py`) |
| `src/` | C: Equivalent files (checked by `tools/equiv.py`, not built) and matching C units (built, see below) |
| `tests/` | Test cases per function (`tests/<file>/<function>.json`) and `tests/equivalent.txt`, the functions found Equivalent |
| `docs/equivalent.md` | The evidence for each Equivalent function (written by `tools/equiv.py`) |
| `sdk-verified.txt` | Library functions whose bytes the SDK source you supplied reproduces (written by `tools/sdk_source.py`) |
| `sdk-source/` | The C of those library functions, from the SDK source you supplied (local, git-ignored) |
| `AGENTS.md` | The per-function decompilation loop: Equivalent first, Matching as the bonus |
| `tools/` | Disc reader, splitter, text mapper, model mapper, C-unit layout, progress report, missed-function finder, SH-4 disassembler and simulator, the Equivalent check (`equiv.py`) with its helpers (`checksizes.py`, `classify.py`, `poollist.py`, `port_equiv.py`), the SDK-source check (`sdk_source.py`), live checks against the running game (optional) |

`text-map/` (generated) lists the executable's strings, how much text each disc file holds, and every image file
(`images.tsv`). Counts and lists for you to read, not a verdict.

## Model map

`setup.sh` also builds `model-map/game.dcgs` (with `tools/model_map.py`): every model it recognises in the disc files, the
table in the executable that holds it, the texture lists, every sound it recognises (CRI ADX and AHX streams, and the sound
banks), and, where a skeleton is known, characters assembled from their parts. It is plain tab-separated text in sections (`[models]`, `[assemblies]`, `[rigs]`, `[bones]`, `[audio]`, `[textures]`) and it is
**committed**: it holds addresses, offsets, sizes and names only, no game bytes or text (the text map is the one
that stays local). Regenerate it with `python3 tools/model_map.py 1ST_READ.BIN "$(cat BASE)" functions.txt "<your disc>.gdi" model-map`.

- **No setup needed to start.** With no rules the map still lists every model it recognises, grouped by the table that holds it.
- **`models.txt` is what is known about the game's models**, one rule per line: `chars` and `structs` (tables whose
  layout is understood), `rig` / `bone` / `assemble` (a skeleton posed from a motion record), `nodes` / `nodelayout` (linked node structs in
  the executable, each character placed in its bind pose), `textures` (pairs a
  model file with a texture file of another name; matching names are found by themselves), `note`, and the two a
  person adds by naming things: `name <file> <offset> <text>` (one model), `sound <file> <entry> <text>` (one sound), `image <file> <offset> <text>` (one picture) and `table <address> <group> <label>`
  (a whole table). The syntax is in the header of `tools/model_map.py`.
- **Naming convention.** A row shows the name first and the id beside it, and only the id when there is no name.
  Names are tidied the same way everywhere: words separated by single spaces (underscores and camelCase become
  spaces), each word starting with a capital, no parentheses. Ids (hex offsets, table addresses, the game's own
  identifiers) are never changed.
- **Naming things.** Edit `models.txt` and rerun the tool, or use a model viewer that opens this folder and writes
  the `name` and `table` lines for you, into two sorted blocks at the end of the file, so a naming session is a small
  `git diff`. Commit the diff.

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
matches. `python3 tools/progress.py` reports the state,
each function in one bucket: done (equivalent C; matching C and SDK source part of it), named only (a name is
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
