# dc-decomp-kickoff

A Claude skill that starts a matching decompilation of a Sega Dreamcast game from your own disc.

You get a repo that:

* rebuilds the game's executable **byte for byte**, from one assembly file per function, with the
  SDK's own Hitachi assembler and linker;
* already names every function it can match by signature (SDK libraries and a reference decomp);
* has a text map for translators: every string with every pointer to it, which disc files hold
  text and which code opens them, and image files that probably have text in them;
* describes the loop for taking functions from assembly to C, with the build checking each step;
* contains **no game code or data**: everything game-derived is generated from your disc.

Worked examples: [crazy-taxi-decomp](https://github.com/consolesplayingconsoles/crazy-taxi-decomp)
and [boku-doraemon-decomp](https://github.com/consolesplayingconsoles/boku-doraemon-decomp). What the
skill did on each game it has been run on is in [`references/evidence.md`](references/evidence.md);
if you run it on a game, the last step prints your run in that format: send it as an issue.

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

The procedure needs a Katana SDK, a reference decomp and an object compare tool. The repositories
named in the skill are identified solely as examples of the type of material required. We have no
affiliation with, and make no representation regarding, those repositories, their contents, or
their licensing. Nothing is retrieved without your confirmation, and you are solely responsible for
determining whether you are entitled to obtain and use any such material.

## Where this comes from

It came out of real work on Consoles Playing Consoles. See what Pluto has helped me build:

- 📸 **Instagram:** [@consolesplayingconsoles](https://www.instagram.com/consolesplayingconsoles/)
- 🔗 **Everything else:** [beacons.ai/consolesplayingconsoles](https://beacons.ai/consolesplayingconsoles)

The [Tokyo Bus Guide decomp](https://github.com/lhsazevedo/tbg-decomp) by
[@lhsazevedo](https://github.com/lhsazevedo), what a champion, is the main reason this works: its build setup runs the
original Hitachi toolchain, its SDK name table was the first map, and it proved a byte-matching
Dreamcast decomp is possible.

## License

© 2026 consolesplayingconsoles. Licensed under **Creative Commons Attribution-ShareAlike 4.0 International** ([CC BY-SA 4.0](LICENSE)): use it, share it, adapt it, as long as you credit the project and share what you build on it under the same licence.
