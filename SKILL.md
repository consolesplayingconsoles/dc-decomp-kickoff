---
name: dc-decomp-kickoff
description: Kick off a matching decompilation of a Sega Dreamcast (Katana) game. Use when someone has a Dreamcast disc and wants a decomp repo started: names applied from SDK signatures and reference decomps, the executable split into one assembly file per function, and a build that reproduces the original byte for byte, ready for agents to decompile function by function.
---

# Kicking off a Dreamcast decomp

The goal is a repo in the best automatable state: it already rebuilds the original executable
byte for byte, every function is its own file, as many as possible carry real names, and the loop
for turning a function into C is written down. Decompiling the game is the work that follows.

## Getting the tools (do this first)

This skill needs its own files (`scripts/`, `template/`, `references/`); the README's install
(the zip from `zip.sh`, or a clone) brings them. If `scripts/split_asm.py` is not next to this file,
only `SKILL.md` was installed: fetch the tools yourself, without asking (they are this skill's own
public code, not third-party material), into a tools folder (default `~/dc-tools`), and tell the
user in one line that you did and that the README's zip install avoids it:

```
git clone https://github.com/consolesplayingconsoles/dc-decomp-kickoff ~/dc-tools/dc-decomp-kickoff
```

Then use that copy for every `scripts/...`, `template/...` and `references/...` path below. Do not
rewrite the tools from this text unless the clone is impossible: they encode fixes that are easy to
get wrong (multi-track discs, link address, regex blowups, linker quirks).

## Read this first: how complete this skill is

**Requirements: Docker and Python 3, on any OS (Mac, Windows, Linux).** Docker is the default:
Ghidra and the Hitachi tools run in containers, so nothing else is installed. Only if Docker is
impossible and the machine is **Linux x86_64**: `DC_LOCAL=1` (opt-in, never a default) runs the
Hitachi tools through `wibo` on PATH and Ghidra from `GHIDRA_INSTALL_DIR` (Ghidra 12.x + JDK 21).
`DC_LOCAL` does not work on macOS or Windows (`wibo` is a Linux program): there, install Docker.
**In a cloud workspace** (a Claude conversation's own Linux machine) images often cannot be pulled:
use `DC_LOCAL=1` for every script (`ref_sigs.sh` and `sdk_unpack.sh` included; the latter also needs
`unshield`), installing wibo (pinned and checksummed as in `scripts/tools-image/Dockerfile`) and
Ghidra + JDK 21 as `scripts/ghidra/Dockerfile` does. The user's disc and SDK images arrive as
uploads or a connected folder; the repo is built there, so offer to hand it back to them at the end.

**Before starting, check the machine:**
- `python3 --version` works and is 3.6 or newer (on macOS, `python3` can be Apple's stub that
  opens an install dialog: then use another Python, e.g. from python.org or Homebrew).
- `docker info` works. Docker Desktop and colima share **only your home folder** with containers
  by default: keep the work folder, the repo and the SDK under your home folder, or mounts arrive
  empty (a build that "can't find" files it plainly has is this).
- About 4 GB free (Docker images ~1.5 GB, the SDK clone, the disc copy for the game image).

**The SDK folder can have any layout** (the reference decomp's `bin/ shc/ shinobi/`, or the
Kochise repository's `.../R10.1_000518/Utl/Dev/Hitachi` + `Lib`): scripts find `asmsh.exe`,
`lbr.exe`, `lnk.exe` and the `.lib` files by name. Point `SDK_PATH` at the SDK's top folder. In the
Kochise repository that is `SDK/EXES/INSTALL KATANA SDK/INPUT/R10.1_000518` (quote it: it has
spaces); a sparse checkout of that folder is enough (`git clone --filter=blob:none --sparse`, then
`git sparse-checkout set "SDK/EXES/INSTALL KATANA SDK/INPUT/R10.1_000518"`).

**A second SDK, optional: 1.55J (1999), for the complete reference decomp and more names.** List it
to the user by its disc names and ask them to provide the images themselves; never download it:
"Dreamcast SDK (Sega Library) Ver.1.55J" **Vol.1 (Common Disc)** and **Vol.2 (For SHC Users)**
(Redump discs 87866 and 87867; Vol.3, CodeWarrior, is not needed). Lay it out with
`python3 scripts/sdk_from_iso.py <out folder> <Vol.1 .iso> <Vol.2 .iso>`: it checks each image
against its Redump record, then copies `bin/` (Vol.1) and `shc/` + `shinobi/` (Vol.2), about a second.
Without it everything below still works, with fewer names.

**Run the Ghidra steps one at a time.** Each needs ~1 GB; Docker Desktop and colima often default to
2 GB, so two at once get killed ("Killed" in the log). `sdk_sigs.sh` switches to one library per run
when Docker has under 4 GB. **Every script fails loudly**: never continue past an empty table.
Ghidra projects are the costly part: `DC_GHIDRA_PROJECTS=<folder>` keeps them there instead of in
the output folder, so cleaning outputs never wipes them (ask the user where, if they have a place).

**Long steps print progress** (Ghidra analysis ~3 min, first build a few minutes, textures a
minute or two): tell the user what is running and roughly how long before starting each.

**Evidence:** what the skill did on each game it has been run on (numbers, what broke, what
changed) is in `references/evidence.md`; the steps below state rules, not games. Everything the
skill uses is in its own folder.

## Third-party sources

The procedure needs three kinds of material. The repositories below are identified solely as
examples of the type of material required. The authors of this skill have no affiliation with, and
make no representation regarding, those repositories, their contents, or their licensing. Nothing
is retrieved without the user's express confirmation. The user is solely responsible for
determining whether they are entitled to obtain and use any such material, and may substitute any
equivalent material lawfully in their possession.

| need | example source | used for |
|---|---|---|
| Katana SDK (libraries + Hitachi `asmsh`, `shc`, `lnk`, `lbr`, `elf2bin`) | `github.com/Kochise/dreamcast-docs` (`SDK/`) | SDK signatures, the matching build |
| other Katana SDK releases, optional (disc images: 0.20 Pre 7 to R11b, 1.55J Vol.1 + Vol.2, Network 1.04; and Katana 0.40 Release.4 for 1998 games) | archive.org item `official-katana-sdks` (`OFFICIAL KATANA SDKs.zip`, one image per release); 1.55J is also catalogued by Redump (discs 87866, 87867); 0.40 from sega-dreamcast-info.com (`Dreamcast Katana SDK Version 0.40 Release.4.zip`) | the release the game was built with (step 2), the complete reference decomp (1.55J), more SDK names |
| a reference decomp | `github.com/consolesplayingconsoles/tbg-decomp` (a fork of `lhsazevedo/tbg-decomp`): latest `main` (the complete decomp, builds with SDK 1.55J) or tag `kickoff-reference-1` (builds with the Kochise R10.1 SDK) | names no SDK copy has |
| object compare tool | `github.com/lhsazevedo/sh4objtest` (MIT) | the C loop (optional) |
| an older SDK, optional | archive.org item `dcsdk-9e` (SDK R9 Europe, Nov 1999, disc 1: SHC 5.1 Release 08) | a period compiler for games built in 1999-2000; so far it gave the same bytes as R10.1's (Release 11) |

Ask before cloning each one. Never commit the SDK, the game's files, or anything derived from them
(hash tables included) to the new repo: its `.gitignore` already excludes them.

## Procedure

0. **Name the conversation after the game.** As soon as IP.BIN gives the title (step 1), rename
   the session if your client lets you (e.g. "Dreamcast decomp kick-off: <title>"), so a user
   running several games can tell the conversations apart.
1. **Disc to executable** (`scripts/gdi_read.py`, CHD via `chdman extractcd`). Check the
   boot file in IP.BIN; `0WINCEOS.BIN` means Windows CE: stop, this skill does not apply.
   **Check it is the game before splitting.** Look for the game's own text (menus, item or place
   names) in the executable. A big `.BIN` next to the boot file can be a bundled application
   instead (a web browser shipped for online registration: `http` strings, a perfect SDK match and
   none of the game's text). A boot file with none of the game's text may only be a core that
   loads the game's code at runtime from other files (relocatable modules): this skill handles one
   executable at a fixed address, so stop and say so (`references/evidence.md` has an example).
2. **Base and fingerprint**: `scripts/linkbase.py`, `scripts/banners.py`. Note the SDK version the game used.
   **Which SDK to ask for:** `python3 scripts/sdk_scan.py references/sdk-banners.tsv <1ST_READ.BIN>`
   ranks the publicly preserved Katana releases by how many of the game's library builds they
   contain. A full match: ask the user for that release. None: say the game was built with a
   release not in the list, and to pick a close one; suggest the one or two the script names. If
   the user already has several SDKs, they can instead point at one folder holding all of them
   (images, zips or folders) and run `sdk_scan.py <that folder> <1ST_READ.BIN>`. Older releases
   ship inside InstallShield cabinets: `scripts/sdk_unpack.sh <image> <out>` lays any of them out
   as plain files (Docker, any OS) before `sdk_sigs.sh`.
3. **Ghidra** (Docker; no Linux machine needed, the image builds on first use), with the
   executable in `<work>`:
   ```
   scripts/ghidra/dghidra.sh <work> /work proj -import /work/1ST_READ.BIN -overwrite \
     -loader BinaryLoader -loader-baseAddr <base> -processor SuperH4:LE:32:default \
     -scriptPath /scripts -preScript DcPre.java -postScript DcReport.java /work/report.txt
   ```
   Import at the base `linkbase.py` picked: at the wrong one Ghidra finds a fraction of the code.
   Never copy the `.java` scripts into `<work>`: Ghidra then finds two copies and fails to load them.
   **How much it finds:** compare the bytes inside functions with the executable's size. A game is
   often mostly data (models, tables), so a third can be normal; a whole region with `rts`
   instructions and no functions is code the analysis never reached. `scripts/seed_funcs.py`
   lists function starts in uncovered stretches; re-import with `-preScript SeedFuncs.java
   <seeds.txt>` after `DcPre.java` so the analysis follows them. Code reached only through switch
   tables (`braf` / `jmp @Rn` with a table of offsets) or runs of function pointers stays hidden
   to both: read those tables when a region still looks like unreached code.
4. **Names**:
   - SDK-wide: `scripts/sdk_sigs.sh <SDK folder> <out>` -> `<out>/katana-sdk.sigs`. Any SDK layout:
     the Hitachi tools and the `.lib` files are found by name. Build once per SDK, keep it local.
     Details and gotchas: `references/sdk-signatures.md`.
     With the 1.55J folder too, run it again into a second folder (`<out155>/katana-sdk.sigs`) and
     apply both tables.
   - Reference decomp: `scripts/ref_sigs.sh <SDK folder> <out> [<SDK 1.55J folder>]` ->
     `<out>/tbg.sigs`. No game disc needed: it clones the decomp (ask first), builds Tokyo Bus
     Guide's executable from it (checked against TBG's SHA-1) and hashes its named functions. With
     1.55J: the complete decomp (the fork's latest `main`, pulled every run), every function its linker map names
     (1,462). Without: tag `kickoff-reference-1` built with R10.1, the 176 library functions its
     link script pins (162 hashable). A few minutes, once.
   - **Apply every table you have, all in one Ghidra run**, then `DcReport.java`:
     1. all the SDK tables merged into one (`cat` them into one file), with `ApplySigs.java <sigs>
        <out> apply`: a hash that two releases name differently stays ambiguous, so twin stubs
        (byte-identical code under unrelated names) are never named by which release has which;
     2. the reference decomp's table with `fill`: it only names functions no SDK table named.
     Only unique matches are applied; the same tables always give the same names. A unique match
     on a tiny function (a few instructions) can still be a collision with unrelated library code:
     report short names that make no sense where they sit (a video-player function in a game that
     plays no video) as suspect, never silently trust them.
5. **The repo: ask the user where to put it.** Suggest a default (a sibling of the current folder,
   named from the IP.BIN title: lowercase, spaces to hyphens, plus `-decomp`, e.g.
   `SOME GAME` -> `<parent>/some-game-decomp`), always written as an **absolute path**. Create it,
   then confirm the resolved absolute path back to the user in one line. From here on, every path
   you show (commands, summaries, the final report) is absolute: never `cd <name>` alone.
   **Split**: `scripts/split_asm.py <1ST_READ.BIN> <base> <report> <repo>`: one `.src` per function,
   data words, exported labels, `objects.txt` in link order.
6. **Make the repo publishable and build it.** A pushed repo holds no game bytes, so it must be
   able to regenerate them from each user's own disc. Into the repo:
   - copy `template/` (`build.sh`, `setup.sh`, `disc.sh`, `textures.sh`, `README.md`, `AGENTS.md`),
     and `template/gitignore` as **`.gitignore`** (shipped without the dot: some installs drop
     dotfiles);
   - copy into `tools/`: `scripts/gdi_read.py`, `split_asm.py`, `text_map.py`, `file_tables.py`,
     `textures.py`, `disc_patch.py`, `apply_bin.py`, `docker_check.sh`, `units.py`, `fill.py`,
     `progress.py`, `missed_funcs.py`, `shdis.py`, the `tools-image/` folder and `scripts/hooks/` as `tools/hooks/` (so a cloned repo builds its own
     tools image, nothing pulled from anyone else);
   - write `sdk.txt`: `scripts/sdk_txt.py <repo>/functions.txt <base> <1ST_READ.BIN>
     <SDK ApplySigs output>` (SDK tables only, not the reference decomp's). It marks the boot block
     and the SDK library block, so `tools/progress.py` reports game code and SDK apart;
   - write the base to `BASE` (hex, no `0x`); `split_asm.py` already wrote `functions.txt`;
   - fill the placeholders: in `setup.sh` and `disc.sh` `@BOOT@` (boot file from IP.BIN) and `@SHA1@` (of that
     file); in `README.md` `@TITLE@`, `@RELEASE@` (IP.BIN: title, product number, version, date,
     region), `@BOOT@`, `@SIZE@`, `@SHA1@`, `@BASE@`, `@SDK@` (main banners), `@FUNCS@`, `@NAMED@`,
     `@NAMED_SDK@`, `@NAMED_REF@`, `@LICENSE@`, and `@PROGRESS@` (after the first `MATCH`: the
     output of `python3 tools/progress.py` in a ``` fence). No `@...@` may remain in those three files
     (`grep -n '@[A-Z_]*@' README.md setup.sh disc.sh`; `tools/` has its own `@N@` tokens, ignore).
     `@NAMED@` = functions whose name is not `FUN_...` (what `split_asm.py` prints). It can exceed
     `@NAMED_SDK@` + `@NAMED_REF@`: small wrappers (thunks) inherit the name of what they call.
   - **ask the user for a licence** for the repo's own code and docs (suggest GPL-3.0-or-later or
     MIT) and add its text as `LICENSE`.
   - `chmod +x build.sh setup.sh tools/hooks/pre-commit` (tell the user; it is one command).
   - write `.env` in the repo with `SDK_PATH="<absolute SDK folder>"` (gitignored, machine-local),
     so the user can rebuild with a plain `bash build.sh` later.
   Then put the original executable in as `1ST_READ.BIN` and run `bash build.sh`. It must print `MATCH`. First run assembles every file (minutes); later runs only
   changed ones. Always invoke scripts with `bash`/`python3`: downloads can lose execute bits.
   Finally prove the published layout works: empty `asm/`, `objects.txt`, `text-map/`, then
   `bash setup.sh <disc.gdi>` and `bash build.sh` again: `MATCH` again.
   Then `python3 tools/missed_funcs.py 1ST_READ.BIN <base> functions.txt`: code the analysis did
   not make into functions (callbacks reached only through tables, getters only through literal
   pools, state handlers merged into a neighbour). Expect hundreds, about half backed by a
   pointer. They matter for C units, whose ends must be function boundaries. Report the count
   and leave the list for review: adding an entry never changes the bytes (still `MATCH`), only
   where files split. `python3 tools/progress.py` gives the starting state.
7. **Text map** (for translators, English included: any language can be a source as well as a
   target): `scripts/text_map.py <1ST_READ.BIN> <base> <report> <repo>/text-map <disc.gdi> [tier]`.
   - `exe_strings.tsv`: every executable string, the functions using it, and every pointer to it
     (what lets a translation move text somewhere bigger instead of fitting the old bytes).
   - `files.tsv`: text density per disc file and the code that opens it (where its offsets live).
   - `font.tsv`: BIOS ROM-font callers and font-looking files.
   - `image_candidates.tsv`: files that probably hold text drawn as images, with the reason.
     **Candidates only; the user decides.** Today's signal: language variants (`SPRMENG`/`SPRMJAP`).
     A single-language game gets an explicit "no automatic signal" line, never an empty file.
   - `file_tables.tsv` (`scripts/file_tables.py`): for each disc file made of repeating records, the
     table in the executable that locates them (bytes or sectors, with or without sizes). **This is
     what lets a container grow:** repack its records, rewrite that table (proof in `references/evidence.md`). No false hits
     so far, but games often keep positions elsewhere: a missing row does not prove there is no table.
   - Textures are their **own step** (`bash textures.sh <disc.gdi>`, seconds to a minute): every
     standard (PVR) texture decoded to PNG on one page with checkboxes (`text-map/textures/`), for a
     person to mark the ones with text. A game that keeps its art in its own formats gets 0 here and a
     note saying so; then `image_candidates.tsv` is the lead.
   - `setup.sh` rebuilds the text map from `functions.txt`, so a cloned repo's `files.tsv` lists
     function-level users only; the kick-off's own run (from the full Ghidra report) has more.
   - Tiers: `quick` = executable only (seconds); `standard` = plus a 2 MiB sample of every disc file
     (seconds to a minute); `deep` = whole files (minutes on a full disc).
   - Density and the Shift-JIS count are heuristics: binary data scores as text sometimes.
   - **OCR is not included, on purpose.** Finding baked text in single-language games would mean
     decoding every texture (PVR, often thousands per disc) and running OCR on each: tens of
     minutes to hours, plus an OCR engine and its Japanese data, and game fonts are stylised, so it
     misses text and flags noise. If a user wants it, warn them of that cost first, and still
     present the results as candidates. A contact sheet of all textures for a human to tick is
     often faster and is the only reliable method.
8. **Game build**: `bash disc.sh <original .gdi>` writes `build/disc/`: a copy of the user's disc
   with the rebuilt executable and every file under `disc/` (same path as on the disc) written in
   place, error correction recomputed, read back to verify. A smaller file is padded; a **bigger**
   one moves into free sectors (GD-ROMs often carry a whole filler track) and its directory entry is
   repointed. To change the executable from a modified copy, `tools/apply_bin.py <repo> <original>
   <modified>` writes the changes into the asm data words; then `bash build.sh` (it prints DIFFERS,
   expected; `DC_EXPECT_CHANGES=1` makes that exit 0).
9. **Hand over**: `template/AGENTS.md` is the loop (names first, then C one source file at a time).
   If the game was later ported and the user has the port (an Android `.apk`, an iOS or PC build),
   offer `references/port-symbols.md`: a port that kept its symbol table names a large share of
   the game's functions and globals by their original names.
   **Print the run as an evidence entry** (the format at the top of `references/evidence.md`:
   game, SDK by banners, counts, MATCH, text-map highlights, and what broke or surprised), and
   tell the user they can send it to the skill's repo as an issue so the next version learns from
   their game. Never write into the skill's own folder.
10. **GitHub (optional)**: print, do not run, the commands for the user:

   ```
   cd "<absolute repo path>" && git init && git config core.hooksPath tools/hooks && git add -A && git commit -m "Kick off: byte-matching split, <n> named"
   # check first: git ls-files must show no asm/, 1ST_READ.BIN or other game files
   gh repo create <owner>/<repo dir name> --public --source . --push
   ```

## Rules
- The build must match before handing over, and after every change.
- Names are only applied on unique matches; ambiguous hashes are listed, never guessed.
- Link order is address order; a file's size never changes unless its replacement matches.

## Scripts

| script | what it does |
|---|---|
| `scripts/gdi_read.py` | list / extract files from any data track of a GDI; extract IP.BIN |
| `scripts/linkbase.py` | pick the import base from self-pointer counts |
| `scripts/banners.py` | SDK module banners: name, version, build date |
| `scripts/ghidra/dghidra.sh` | headless Ghidra in Docker (image from `scripts/ghidra/Dockerfile`, built on first use) |
| `scripts/ghidra/*.java` | seed + report (`DcPre`, `DcReport`), signatures (`ExportSigs`, `ApplySigs`), queries (`Query`) |
| `references/sdk-signatures.md` | naming library code from a reference decomp or the SDK's libraries |
| `references/evidence.md` | each game the skill was run on: numbers, what broke, what changed |
| `references/memory-map.md` | Dreamcast addresses worth labelling on sight |
| `references/matching-c.md` | getting a source file to match: units, flags, fill, idioms, compare loop |
| `references/port-symbols.md` | naming from a later port that kept its symbols (Android, iOS, PC builds) |
| `scripts/ref_sigs.sh` | reference decomp names: build TBG's executable from the decomp, hash its named functions |
| `scripts/sdk_sigs.sh` | signature table for every exported function in an SDK's libraries |
| `scripts/sdk_from_iso.py` | SDK 1.55J folder from its Vol.1 + Vol.2 disc images, checked against Redump |
| `scripts/sdk_scan.py` | which SDK release built the game: its library banners against `references/sdk-banners.tsv` or a folder of SDKs |
| `scripts/sdk_unpack.sh` | any SDK image or zip as plain files, InstallShield cabinets unpacked (`unshield-image/`) |
| `scripts/iso_extract.py` | copy every file out of a disc image or zip (Joliet or ISO9660, no mounting) |
| `references/sdk-banners.tsv` | library banners (module, version, build date) of every preserved Katana release |
| `scripts/text_map.py` | strings with pointers, file text density, font path, image candidates |
| `scripts/file_tables.py` | tables in the executable that locate records inside disc files |
| `scripts/textures.py` | every standard texture to PNG + a contact sheet (`index.html`) |
| `scripts/disc_patch.py` | copy a GDI with files replaced in place, error correction recomputed |
| `template/disc.sh` | in the repo: build a playable disc image of the user's version |
| `template/textures.sh` | in the repo: the texture contact sheet, as its own step |
| `scripts/apply_bin.py` | write a modified executable's changes into the repo's asm data words |
| `scripts/docker_check.sh` | Docker installed vs running vs low memory, and the tools image on first use |
| `scripts/tools-image/Dockerfile` | the `dc-tools` image: small Linux + pinned, checksum-verified wibo |
| `scripts/split_asm.py` | split an executable into per-function asmsh sources + link order |
| `template/build.sh` | assemble, compile C units, link (`start P(<base>)`), `elf2bin`, compare with the original |
| `scripts/units.py` | in the repo: the link order with C units in place of the asm files they replace |
| `scripts/fill.py` | in the repo: lay a C unit out like the original (nop alignment, 0xEE fill, exact size) |
| `scripts/progress.py` | in the repo: matching C, named functions and globals, documented, game and SDK apart |
| `scripts/sdk_txt.py` | mark the SDK's code (boot block, library block, single matches) as `sdk.txt` |
| `scripts/missed_funcs.py` | list code the analysis did not make into functions |
| `scripts/seed_funcs.py` | function starts in stretches no function covers, seeds for `ghidra/SeedFuncs.java` |
| `scripts/shdis.py` | in the repo: SH-4 disassembly with FPU, pool values and names (stdlib) |
| `scripts/map_names.py` | code symbols of a linked library's map, runtime routines included |
| `scripts/ghidra/ExportFeatures.java` | per-function strings, constants, calls and globals, for port matching |
| `scripts/port/*.py` | pair functions and globals with a port's symbols (`references/port-symbols.md`) |
| `template/setup.sh` | in the repo: extract + verify the user's executable, regenerate `asm/` and `text-map/` |
| `template/README.md` | the repo's README, with `@PLACEHOLDERS@` to fill |
| `template/AGENTS.md` | the decompilation loop for whoever works in the repo |
| `template/gitignore` | the repo's `.gitignore`: keeps game and SDK material out of git (asm, executable, disc, build, text map) |
