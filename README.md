# dc-decomp-kickoff

A Claude skill that starts a decompilation of a Sega Dreamcast game from your own disc: a repo where
a function is done when its C **behaves like the original** (proven in an SH-4 simulator), with
byte-identical C as the bonus tier.

## What you get

The repo it makes:

| # | Feature | What it does |
|---|---|---|
| 1 | Byte-for-byte rebuild | Rebuilds the game's executable **byte for byte**, from one assembly file per function, with the SDK's own Hitachi assembler and linker (the baseline: the build keeps matching as C replaces assembly). |
| 2 | Names | Already names every function it can match by signature (the SDK's own libraries). |
| 3 | Text map | For translators: every string with every pointer to it, which disc files hold text and which code opens them, and image files that probably have text in them. |
| 4 | Model map | Every 3D model in the disc files (the NAOMI library's format), the table in the executable that holds each, the texture lists, and characters assembled from a known skeleton, in one plain-text file, `model-map/game.dcgs`. It starts with no knowledge of the game, and a `models.txt` per game records what people learn (tables, names): anyone can run the skill, name what they recognise and commit it back. |
| 5 | Equivalent C | Describes the loop for taking functions from assembly to C, with the build checking each step, and `tools/equiv.py` checking each function's C against the original (calls, memory writes and result, on test cases, in an SH-4 interpreter). **Equivalent C** is what counts as done, so a function can be decompiled and proven without reproducing the compiler's exact output. |
| 6 | Tools | The tools that made that fast: size, instruction and literal-pool checks per function, and `port_equiv.py`, which carries a sibling decomp's verified C for shared library code (the NAOMI library, the C runtime) into a new one, each function checked again on the new game's own bytes. |
| 7 | Asset choice | The kickoff asks which asset kinds to map, **All** first. You opt out, never in. |
| 8 | No game code or data | What carries the game's bytes or text is generated from your disc and kept out of git; what only describes it (addresses, sizes, names, the model map) is committed. |

## What is in this folder

| Path | What |
|---|---|
| `SKILL.md` | The procedure Claude follows. |
| `scripts/` | The tools it runs and copies into each repo's `tools/`: disc reader, splitter, text and model mappers, SH-4 simulator, the Equivalent check and its helpers. |
| `template/` | What each new repo starts from: `build.sh`, `setup.sh`, `disc.sh`, `textures.sh`, `models.txt`, `README.md`, `AGENTS.md`, `gitignore`. |
| `references/` | Evidence from every game it has run on, SDK notes, the Equivalent pipeline, the memory map. |
| `zip.sh`, `dist/` | Builds the zip you upload to claude.ai. |
| `VERSION`, `LICENSE` | The kickoff version a repo records, and the licence. |

## Worked examples

| Game | Repo |
|---|---|
| Crazy Taxi | [crazy-taxi-decomp](https://github.com/consolesplayingconsoles/crazy-taxi-decomp) |
| Virtua Tennis | [virtua-tennis-decomp](https://github.com/consolesplayingconsoles/virtua-tennis-decomp) |
| Boku Doraemon | [boku-doraemon-decomp](https://github.com/consolesplayingconsoles/boku-doraemon-decomp) |

| Read | What it is |
|---|---|
| [`references/evidence.md`](references/evidence.md) | What the skill did on each game it has been run on. If you run it on a game, the last step prints your run in that format: send it as an issue. |
| [`references/equivalent-pipeline.md`](references/equivalent-pipeline.md) | How Equivalent C is written fast, and checked, at scale. |

## Install

The skill is a folder: `SKILL.md` plus the `scripts/`, `template/` and `references/` it runs.
Install the whole folder, not `SKILL.md` alone.

* **Claude (claude.ai or the desktop app):** build the zip, then upload it as a skill (Settings,
  Capabilities, Skills):
  ```
  git clone https://github.com/consolesplayingconsoles/dc-decomp-kickoff
  bash dc-decomp-kickoff/zip.sh
  ```
  It writes `dc-decomp-kickoff/dist/dc-decomp-kickoff.zip`. Then ask Claude to start a decomp of
  your game. The work runs in Claude's own workspace, so you upload your disc and SDK images there
  when it asks.
* **Claude Code:** clone it into your skills folder, then ask Claude to start a decomp of your game:
  ```
  git clone https://github.com/consolesplayingconsoles/dc-decomp-kickoff ~/.claude/skills/dc-decomp-kickoff
  ```
  The work runs on your machine, with your disc and SDK where they already are.

If only `SKILL.md` got installed, the skill fetches its own tools from this repo before starting.

**What you provide:** your game disc (`.gdi` or `.chd`) and a Katana SDK. The skill reads your
disc and tells you which SDK release it was built with, so you know which one to get. You also
need Docker and Python 3 wherever it runs (Claude's workspace has them).

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

## License

© 2026 consolesplayingconsoles. Licensed under **Creative Commons Attribution-ShareAlike 4.0 International** ([CC BY-SA 4.0](LICENSE)): use it, share it, adapt it, as long as you credit the project and share what you build on it under the same licence.
