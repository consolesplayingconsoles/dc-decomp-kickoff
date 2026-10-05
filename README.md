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

Worked example: [crazy-taxi-decomp](https://github.com/consolesplayingconsoles/crazy-taxi-decomp)
(2,389 functions, 430 named, byte-identical rebuild).

Start with [`SKILL.md`](SKILL.md). Requirements: Docker and Python 3, on any OS.

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

The Tokyo Bus Guide decomp by lhsazevedo is the main reason this works: its build setup runs the
original Hitachi toolchain, its SDK name table was the first map, and it proved a byte-matching
Dreamcast decomp is possible.

## License

© 2026 consolesplayingconsoles. Licensed under **Creative Commons Attribution-ShareAlike 4.0 International** ([CC BY-SA 4.0](LICENSE)): use it, share it, adapt it, as long as you credit the project and share what you build on it under the same licence.
