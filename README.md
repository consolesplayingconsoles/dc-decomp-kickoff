# dc-decomp-kickoff

Give Claude your Dreamcast game disc and a Katana SDK, and it kicks off the decompilation project of your game from zero, giving you and your AI agents a fully formed repo with everything you need to start decompiling: function names, mappings, asset references, documentation for AI agents, and the whole toolchain running in Docker. Welcome to 1998.

> A new decomp project will start at a range of 0-10% depending on the game and the extras provided (SDK sources, prototypes, ports...). Zombie Revenge for example started at 6.5% with SDK sources alone.
 
The output repo rebuilds the game's executable byte for byte, names what it can match, and maps the game's
text, 3D models and sounds, so you start by reading and naming instead of setting up. A function counts as done when
its C **behaves like the original** (proven in an SH-4 simulator), with byte-identical C as the bonus tier.

You get a repo that:

| # | Feature                        | Does this                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
|---|--------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | Byte-for-byte rebuild          | Rebuilds the game's executable **byte for byte**, from one assembly file per function, with the SDK's own Hitachi assembler and linker (the baseline: the build keeps matching as C replaces assembly).                                                                                                                                                                                                                                                                                                                                                 |
| 2 | Names                          | Already names every function it can match by signature (the SDK's own libraries).                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| 3 | Text map                       | Has a text map for translators: every string in the executable with every pointer to it, how much text each disc file holds and which code opens it, and a list of every image file.                                                                                                                                                                                                                                                                                                                                                                    |
| 4 | Model map                      | Has a model map: every model it recognises in the disc files (the NAOMI library's flat format, Ninja models and motions, object trees stored as a memory image, and a few other common formats), the table in the executable that holds each, the texture lists, and characters assembled from a known skeleton, in one plain-text file, `model-map/game.dcgs`. It starts with no knowledge of the game, and a `models.txt` per game records what people learn (tables, names): whoever runs the skill can name what they recognise and commit it back. |
| 5 | Audio map                      | Lists every sound it recognises: CRI ADX and AHX streams, WAV files, sample streams, and the DTPK, SMLT and SMPB sound banks, in archives or on their own, with channels, sample rate and length. The archives carry no names, so a sound is named the same way a model is.                                                                                                                                                                                                                                                                             |
| 6 | Equivalent C                   | Describes the loop for taking functions from assembly to C, with the build checking each step, and `tools/equiv.py` checking each function's C against the original (calls, memory writes and result, on test cases, in an SH-4 interpreter): **Equivalent C** is what counts as done, so a function can be decompiled and proven without reproducing the compiler's exact output.                                                                                                                                                                      |
| 7 | Tools                          | Has the tools that made that fast: size, instruction and literal-pool checks per function, and `port_equiv.py`, which carries a sibling decomp's verified C for shared library code (the NAOMI library, the C runtime) into a new one, each function checked again on the new game's own bytes.                                                                                                                                                                                                                                                         |
| 8 | Progress                       | Reports one status the same way for every project: done (equivalent C), matching C, named and documented, so projects compare.                                                                                                                                                                                                                                                                                                                                                                                                                          |
| 9 | Git-ignored game code and data | Keeps the game's code and data out of git: what carries its bytes or text is generated from your disc, or from your SDK's sources, and git-ignored; what only describes it (addresses, sizes, names, the model map) is committed.                                                                                                                                                                                                                                                                                                                       |

**Note:** given the volume of data the skill needs, and since Claude will not download games, SDKs or any extra that contains IP.
Sharing the heavy files with Claude becomes tricky: you either need a paid account, 
or a workaround to share files with the sandboxed Claude. 
Even on a paid account, execution time and file size limits apply. Claude Code is preferred. Claude chat will work but is less automatic. 
It will ask you to run certain commands yourself.

Future versions of dc-decomp-kickoff could include a workaround when found, please share ideas if you have any.

## What it reads

| Map        | Reads today                                                                                                                                                       | Otherwise                                                             |
|------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| Executable | A boot file with the game at a fixed address                                                                                                                      | A game that loads its code from other files stops at step 1, like PSO |
| Text       | ASCII and Shift-JIS strings, with every pointer to them                                                                                                           | Other encodings and compressed text are counted per file              |
| Models     | The NAOMI library's flat format, Ninja models and motions, object trees stored as a memory image, tagged model blocks, PRM and TR4 meshes, ZIP and Quake 3 models | Other formats are not listed                                          |
| Textures   | PowerVR twiddled and VQ, through the executable's own lists, a model file's own lists, or a `textures` rule                                                       | Other formats are listed in `images.tsv`                              |
| Audio      | CRI ADX and AHX streams, WAV, sample streams, DTPK, SMLT and SMPB banks                                                                                           | Other formats are not listed                                          |

Found a game outside these? Open an issue with what you've worked out about its format, or open a pull request. Every game contributes to improving future decomps for everyone.

## What is in this repository

| Path                         | What                                                                                                                                                         |
|------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`SKILL.md`](SKILL.md)       | The procedure Claude follows.                                                                                                                                |
| [`scripts/`](scripts/)       | The tools it runs and copies into each repo's `tools/`: disc reader, splitter, text and model mappers, SH-4 simulator, the Equivalent check and its helpers. |
| [`template/`](template/)     | What each new repo starts from: `build.sh`, `setup.sh`, `disc.sh`, `textures.sh`, `models.txt`, `README.md`, `AGENTS.md`, `KICKOFF`, `gitignore`.            |
| [`references/`](references/) | Evidence from every game it has run on, SDK notes, the Equivalent pipeline, the memory map.                                                                  |
| [`VERSION`](VERSION)         | The skill's version (each repo records the one it is at in `KICKOFF`; [upgrading](references/upgrade.md) brings it to a newer one).                          |

## Worked examples

| Game                        | Release                  | Repo                                                                                        | What it is                                                                                                                                | Evidence                                                                        |
|-----------------------------|--------------------------|---------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| Crazy Taxi                  | Europe, MK-51035, V1.000 | [crazy-taxi-decomp](https://github.com/consolesplayingconsoles/crazy-taxi-decomp)           | A decomp built for modding: named functions and globals, functions proven as Equivalent C, and a model map                                | [Evidence](references/evidence.md#crazy-taxi-europe)                            |
| Virtua Tennis               | USA, MK-51054, V1.001    | [virtua-tennis-decomp](https://github.com/consolesplayingconsoles/virtua-tennis-decomp)     | A decomp started beside Crazy Taxi, which shares its library with it, for a combined mod: the same names, Equivalent C and model map      | [Evidence](references/evidence.md#virtua-tennis-usa-mk-51054-v1001)             |
| Boku Doraemon               | Japan, T-41802M, V1.003  | [boku-doraemon-decomp](https://github.com/consolesplayingconsoles/boku-doraemon-decomp)     | An experiment: a translation target                                                                                                       | [Evidence](references/evidence.md#boku-doraemon-japan-t-41802m-v1003)           |
| Illbleed                    | Japan, T45601M, V1.003   | [illbleed-decomp](https://github.com/consolesplayingconsoles/illbleed-decomp)               | An experiment: a second translation target, also doable                                                                                   | [Evidence](references/evidence.md#illbleed-japan-crazy-games-t45601m-v1003)     |
| Sonic Adventure             | Europe, MK-51000, V1.003 | [sonic-adventure-decomp](https://github.com/consolesplayingconsoles/sonic-adventure-decomp) | A kickoff run: names and maps (text, models, textures, sounds), no function decompiled yet                                                | None yet                                                                        |
| Zombie Revenge              | Europe, MK-51038, V1.000 | [zombie-revenge-decomp](https://github.com/consolesplayingconsoles/zombie-revenge-decomp)   | A kickoff run: 6.5% done from the SDK source alone, plus a model map                                                                      | None yet                                                                        |
| Virtua Fighter 3            | US, MK-51001, V1.002     | [vf3-decomp](https://github.com/celsowm/vf3-decomp) (another team's)                        | An experiment: names for their decomp ([the merged PR](https://github.com/celsowm/vf3-decomp/pull/1))                                     | [Evidence](references/evidence.md#virtua-fighter-3tb-us-mk-51001-v1002)         |
| Phantasy Star Online Ver. 2 | US, MK-51193, V1.004     | None                                                                                        | **Not compatible**: the boot file has none of the game's code, which loads from over 600 files at runtime, so the kickoff stops at step 1 | [Evidence](references/evidence.md#phantasy-star-online-ver-2-us-mk-51193-v1004) |

## Evidence and method

The evidence behind the examples above, and the method the repos follow.

|   | Read                                                                     | What it is                                                                                                                                      |
|:--|--------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|
|   | [`references/evidence.md`](references/evidence.md)                       | What the skill did on each game it has been run on. If you run it on a game, the last step prints your run in that format: send it as an issue. |
|   | [`references/equivalent-pipeline.md`](references/equivalent-pipeline.md) | How Equivalent C is written fast, and checked, at scale.                                                                                        |

## Install

The skill is a folder: [`SKILL.md`](SKILL.md) plus the [`scripts/`](scripts/), [`template/`](template/) and [`references/`](references/) it runs.
Install the whole folder when possible. Where only [`SKILL.md`](SKILL.md) can be added, the skill fetches the rest itself.

* **Claude Code:** clone it into your skills folder, then run `/dc-decomp-kickoff` to start a decomp of your game:
  ```
  git clone https://github.com/consolesplayingconsoles/dc-decomp-kickoff ~/.claude/skills/dc-decomp-kickoff
  ```
  The work runs on your machine, with your game and SDK images where they already are.

If only [`SKILL.md`](SKILL.md) got installed, the skill fetches its own tools from this repo before starting.

**What you provide:** the game disc as a `.gdi` with its track files (only `.gdi`) and a Katana SDK. The skill reads the disc and reports which SDK
release it was built with; that release's library sources, or those of another release, are accepted as well. Not all
games have a later port or a prototype, but where they do, providing them is encouraged, as they can be the strongest
source of information available. Skipping the optional steps can result in a weaker kickoff output. Python 3 is required
wherever it runs, and Docker on any OS. Without Docker (Linux x86_64 only), `scripts/setup_tools.sh` installs the tools
the skill needs, one step at a time.

**Optional, and worth having:** each of these gives the decomp a stronger starting point. The skill asks for them
one by one (a path, a link, or "no"), and only uses what you give it: it never fetches games, SDKs or any other material that contains IP.

| # | Material                                               | What it gives you                                                                                                                                                                                                          |
|---|--------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | A later port                                           | The big one when it kept its symbol table: it can name a large share of the functions and globals. **Android** (an `.apk`) is particularly effective; **PC** ports rarely carry symbols. iOS and other consoles count too. |
| 2 | A prototype, debug build or dev kit dump               | Pre-release discs sometimes carry the linker's `.ELF` or `.MAP`, or a build log, with every name. Debug text left in early builds names what it prints.                                                                    |
| 3 | Cheat codes for the game                               | A saved code list (CodeBreaker or Xploder format, or a saved gamehacking.org page). Every code is an address with a meaning: named variables. Widescreen codes count too.                                                  |
| 4 | Other regions or revisions                             | The same code, so names and addresses carry across.                                                                                                                                                                        |
| 5 | Existing reverse-engineering notes or a partial decomp | A repo, thread or wiki page: reference names and pitfalls.                                                                                                                                                                 |
| 6 | A decomp of the same game on another console           | Structures, class names and logic; no bytes match.                                                                                                                                                                         |

## Third-party sources

The procedure needs a Katana SDK. The repositories
named in the skill are identified solely as examples of the type of material required. We have no
affiliation with, and make no representation regarding, those repositories, their contents, or
their licensing. Nothing is retrieved without your confirmation, and you are solely responsible for
determining whether you are entitled to obtain and use any such material.

## Where this comes from

It came out of real work on Consoles Playing Consoles. See what Pluto has helped me build:

- 📸 **Instagram:** [@consolesplayingconsoles](https://www.instagram.com/consolesplayingconsoles/)
- 🔗 **Everything else:** [beacons.ai/consolesplayingconsoles](https://beacons.ai/consolesplayingconsoles)
