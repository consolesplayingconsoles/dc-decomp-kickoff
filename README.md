# dc-decomp-kickoff

Give Claude your Dreamcast game disc and a Katana SDK, and it starts the decompilation of your game and guides your AI agent to completion. The repo rebuilds the
executable byte for byte, with function names, maps of the game's text, models and sounds, and documentation for you and your
agent. Welcome to 1998.

The process was worked out on real Dreamcast decomps and is refined with every game that goes through it, so each decomp is easier than the last.

A function counts as done when its C **behaves like the original** (proven in an SH-4 simulator, with the share of the original's
instructions the test cases ran reported beside it); byte-identical C is the bonus tier.

## The decompilation steps

Claude uses the dc-decomp-kickoff skill to start the repo and follows these steps. **Following them can guide you all the way to 100%**, and you are free to fork at any moment and
follow your own strategy. Every step ends by printing the project's progress.
  
| # | Step                                    | Decomp completion         | You provide                        | What it does                                                                                                                                                                                                                                                                                                               |
|---|-----------------------------------------|---------------------------|------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | **Decomp project setup**                | -                         | The disc as a `.gdi`, a Katana SDK | Installs the tools (Docker, Python 3) and checks your game disc and SDK.                                                                                                                                                                                                                                                   |
| 2 | **Signature-driven baseline**           | -                         |                                    | Reads the disc, splits the executable into one assembly file per function, rebuilds it **byte for byte** with the SDK's own assembler and linker, and names every function it can match by signature.                                                                                                                      |
| 3 | **Asset mapping**                       | -                         |                                    | Writes the text map (every string with its pointers, text per disc file), the model map, the texture list and the audio map.                                                                                                                                                                                               |
| 4 | **Opportunity-driven optional boosts**  | Varies greatly by project | The materials                      | Uses what you hand over to save work in every step after it, the earlier the better: a later port (Android is the strongest), a prototype or debug build, cheat codes, other regions, existing notes, the same game on another console, a sibling decomp. It never looks for these itself and never reads your other code. |
| 5 | **Incremental script-generated decomp** | ~25% (higher with boosts) | SDK library sources (optional)     | Proves C for what the tools can write on their own: the SDK's own library source where you have it, then script-generated C, then a second pass that draws the test cases again to cover more of the original. Script-generated C is reported apart from agentic C.                                                        |
| 6 | **Experience-driven agentic decomp**    | 100%                      |                                    | Takes what is left one pocket at a time, function by function: C and test cases until each function is proven. The plan is in the repo's `AGENTS.md`.                                                                                                                                                                      |

**Note:** dc-decomp-kickoff never downloads games, SDKs or any material that contains IP, and the heavy files are yours to hand over. Claude Code is preferred: Claude chat is less automatic and will ask you to run some commands yourself.

## What it reads

| Map        | Reads today                                                                                                                                                       | Otherwise                                                             |
|------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------|
| Executable | A boot file with the game at a fixed address                                                                                                                      | A game that loads its code from other files stops at step 1, like PSO |
| Text       | ASCII and Shift-JIS strings, with every pointer to them                                                                                                           | Other encodings and compressed text are counted per file              |
| Models     | The NAOMI library's flat format, Ninja models and motions, object trees stored as a memory image, tagged model blocks, PRM and TR4 meshes, ZIP and Quake 3 models | Other formats are not listed                                          |
| Textures   | PowerVR twiddled and VQ, through the executable's own lists, a model file's own lists, or a `textures` rule                                                       | Other formats are listed in `images.tsv`                              |
| Audio      | CRI ADX and AHX streams, WAV, sample streams, DTPK, SMLT and SMPB banks                                                                                           | Other formats are not listed                                          |

## Worked examples

| Game                        | Release                  | Repo                                                                                        | What it is                                                                                                                                | Evidence                                                                        |
|-----------------------------|--------------------------|---------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| Crazy Taxi                  | Europe, MK-51035, V1.000 | [crazy-taxi-decomp](https://github.com/consolesplayingconsoles/crazy-taxi-decomp)           | A decomp built for modding: named functions and globals, functions proven as Equivalent C, and a model map                                | [Evidence](references/evidence.md#crazy-taxi-europe)                            |
| Virtua Tennis               | USA, MK-51054, V1.001    | [virtua-tennis-decomp](https://github.com/consolesplayingconsoles/virtua-tennis-decomp)     | A decomp started beside Crazy Taxi, which shares its library with it, for a combined mod: the same names, Equivalent C and model map      | [Evidence](references/evidence.md#virtua-tennis-usa-mk-51054-v1001)             |
| Boku Doraemon               | Japan, T-41802M, V1.003  | [boku-doraemon-decomp](https://github.com/consolesplayingconsoles/boku-doraemon-decomp)     | An experiment: a translation target                                                                                                       | [Evidence](references/evidence.md#boku-doraemon-japan-t-41802m-v1003)           |
| Illbleed                    | Japan, T45601M, V1.003   | [illbleed-decomp](https://github.com/consolesplayingconsoles/illbleed-decomp)               | An experiment: a second translation target, also doable                                                                                   | [Evidence](references/evidence.md#illbleed-japan-crazy-games-t45601m-v1003)     |
| Sonic Adventure             | Europe, MK-51000, V1.003 | [sonic-adventure-decomp](https://github.com/consolesplayingconsoles/sonic-adventure-decomp) | Names and maps (text, models, textures, sounds)                                                                                           | None yet                                                                        |
| Zombie Revenge              | Europe, MK-51038, V1.000 | [zombie-revenge-decomp](https://github.com/consolesplayingconsoles/zombie-revenge-decomp)   | Names, the SDK's own source verified, and a model map                                                                                     | None yet                                                                        |
| Virtua Fighter 3            | US, MK-51001, V1.002     | [vf3-decomp](https://github.com/celsowm/vf3-decomp) (another team's)                        | An experiment: names for their decomp ([the merged PR](https://github.com/celsowm/vf3-decomp/pull/1))                                     | [Evidence](references/evidence.md#virtua-fighter-3tb-us-mk-51001-v1002)         |
| Phantasy Star Online Ver. 2 | US, MK-51193, V1.004     | None                                                                                        | **Not compatible**: the boot file has none of the game's code, which loads from over 600 files at runtime, so the kickoff stops at step 1 | [Evidence](references/evidence.md#phantasy-star-online-ver-2-us-mk-51193-v1004) |

## Evidence and method

- [references/evidence.md](references/evidence.md): Records what dc-decomp-kickoff did on each game it has run on. If you run your own decomp please share the generated evidence so the tool can grow.

- [references/equivalent-pipeline.md](references/equivalent-pipeline.md): Explains how Equivalent C is written and checked at scale. [SKILL.md](SKILL.md) is the procedure Claude follows;

- [scripts/](scripts/), [template/](template/) and [references/](references/): hold what it runs and copies into each repo.

## Install

dc-decomp-kickoff is a skill folder: [SKILL.md](SKILL.md) plus the [scripts/](scripts/), [template/](template/) and [references/](references/) it runs.
Install the whole folder when possible. Where only [SKILL.md](SKILL.md) can be added, dc-decomp-kickoff fetches the rest itself.

* **Claude Code:** clone it into your skills folder, then run `/dc-decomp-kickoff` to start a decomp of your game:
  ```
  git clone https://github.com/consolesplayingconsoles/dc-decomp-kickoff ~/.claude/skills/dc-decomp-kickoff
  ```
  The work runs on your machine, with your game and SDK images where they already are.

**What you provide:** the game disc as a `.gdi` with its track files (only `.gdi`) and a Katana SDK. dc-decomp-kickoff reads the disc and reports which SDK
release it was built with; that release's library sources, or those of another release, are accepted as well. Not all
games have a later port or a prototype, but where they do, providing them is encouraged, as they can be the strongest
source of information available. Skipping the optional boosts means more work in the later steps. Python 3 is required
wherever it runs, and Docker on any OS. Without Docker (Linux x86_64 only), `scripts/setup_tools.sh` installs the tools
dc-decomp-kickoff needs, one step at a time.

**Optional, and worth having:** each of these saves work, and the earlier it is used the more it saves (the SDK's own source is the clearest case). dc-decomp-kickoff asks for them
one by one (a path, a link, or "no"), and only uses what you give it: it never fetches games, SDKs or any other material that contains intellectual property.

| # | Material                                               | What it gives you                                                                                                                                                                                                          |
|---|--------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1 | A later port                                           | The big one when it kept its symbol table: it can name a large share of the functions and globals. **Android** (an `.apk`) is particularly effective; **PC** ports rarely carry symbols. iOS and other consoles count too. |
| 2 | A prototype, debug build or dev kit dump               | Pre-release discs sometimes carry the linker's `.ELF` or `.MAP`, or a build log, with every name. Debug text left in early builds names what it prints.                                                                    |
| 3 | Cheat codes for the game                               | A saved code list (CodeBreaker or Xploder format, or a saved gamehacking.org page). Every code is an address with a meaning: named variables. Widescreen codes count too.                                                  |
| 4 | Other regions or revisions                             | The same code, so names and addresses carry across.                                                                                                                                                                        |
| 5 | Existing reverse-engineering notes or a partial decomp | A repo, thread or wiki page: reference names and pitfalls.                                                                                                                                                                 |
| 6 | A decomp of the same game on another console           | Structures, class names and logic; no bytes match.                                                                                                                                                                         |
| 7 | A sibling decomp                                       | Names for library code shared with another game from the same team: exact matches only, from a repo you name.                                                                                                              |

## Third-party sources

The procedure needs a Katana SDK. The repositories
named in dc-decomp-kickoff are identified solely as examples of the type of material required. We have no
affiliation with, and make no representation regarding, those repositories, their contents, or
their licensing. Nothing is retrieved without your confirmation, and you are solely responsible for
determining whether you are entitled to obtain and use any such material.

## Where this comes from

It came out of real work on Consoles Playing Consoles. See what Pluto has helped me build:

- 📸 **Instagram:** [@consolesplayingconsoles](https://www.instagram.com/consolesplayingconsoles/)
- 🔗 **Everything else:** [beacons.ai/consolesplayingconsoles](https://beacons.ai/consolesplayingconsoles)
