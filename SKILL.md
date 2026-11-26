---
name: dc-decomp-kickoff
description: "Kick off and run the decompilation of a Sega Dreamcast (Katana) game (a byte-identical build; functions done when their C is equivalent to the original or matches its bytes). Use when someone has a Dreamcast disc and wants a decomp project: names applied from SDK signatures, the executable split into one assembly file per function, a build that reproduces the original byte for byte, asset maps, and the C proven function by function, then built into the game, in ten steps."
---

# Kicking off a Dreamcast decomp

The goal is a decomp that goes from the disc to proven C for every function, and then to the game built from that C, in ten steps: it rebuilds the original executable
byte for byte, every function is its own file, the names come from the SDK, and the C is proven function by function.
A function is done when its C is **Equivalent** (`tools/sim/equiv.py` runs both
in an SH-4 interpreter on test cases and compares calls, writes and result) or **Matching** (its C rebuilds the original
bytes, one source file at a time). The repo's `MODE` in `status.txt` says which. The repo's build keeps matching the original either way.

## The steps (hard rules)

Every run follows these ten steps, in this order, under these exact titles: six to proven C for every function, then three to build,
run and stabilise the game from it, then the native port. They are the milestones of the run, and the README table lists the same ten. The user can stop after any step or fork into their own strategy; you never skip a step, reorder them or merge them.

| # | Title                               | What it covers                                                                                          | Where                                                 |
|---|-------------------------------------|---------------------------------------------------------------------------------------------------------|-------------------------------------------------------|
| 1 | Decomp project setup                | the tools, the disc, the executable and its base, which SDK, where the repo goes                        | [Step 1](#step-1-decomp-project-setup)                |
| 2 | Signature-driven baseline           | Ghidra, SDK names and types, the split, the repo and a byte-matching build, the game build              | [Step 2](#step-2-signature-driven-baseline)           |
| 3 | Asset mapping                       | text, model, texture and audio maps                                                                     | [Step 3](#step-3-asset-mapping)                       |
| 4 | Opportunity-driven optional boosts  | cheat codes, other regions, notes, a later port, a prototype, a sibling decomp                          | [Step 4](#step-4-opportunity-driven-optional-boosts)  |
| 5 | Incremental script-generated decomp | the SDK's library source, generated C, the polish pass                                                  | [Step 5](#step-5-incremental-script-generated-decomp) |
| 6 | Experience-driven agentic decomp    | the hand-over, the repo's `AGENTS.md`, the loop                                                         | [Step 6](#step-6-experience-driven-agentic-decomp)    |
| 7 | Code size reduction                 | the proven C made small enough to fit where the original code was, still proven                         | [Step 7](#step-7-code-size-reduction)                 |
| 8 | Build from C                        | the executable built from the C, the image checks, a disc to play                                       | [Step 8](#step-8-build-from-c)                        |
| 9 | Runtime repairs                     | the disc run on the console or an emulator, each stop traced to its function and its step, `status.txt` | [Step 9](#step-9-runtime-repairs)                     |
| 10 | Native port                        | tooling to run the game on a host from the proven C                          | [Step 10](#step-10-native-port)                       |

How a step is run:
1. **List the steps to the user, with their titles, before anything starts.**
2. **Delimit every step.** Print `=== Step N of 10: <title> ===` and one line on what it will do before it, and
   `=== Step N of 10 done: <title> ===` after it.
3. **Report results at the end of every step**, with the numbers from `python3 tools/progress.py` (Equivalent C with generated and
   hand-written C apart, matching C, named, and the instruction coverage `equiv.py` reports). A step with nothing to count says so.
4. **The user decides** at each boundary whether to go on. Interrupting is their risk; you repair nothing and keep no rollback state.
5. **Never look into the user's other code** (other repos, ports, prototypes, sibling decomps). Step 4 is an offer: use only what the
   user names or hands over.
6. **Step 6 hands over and continues.** Write the plan into the repo's `AGENTS.md` (what is left, by pocket: library, game code,
   runtime and tables). If the user chooses to continue in this session, `AGENTS.md` is your instructions from there on; if they open a
   new session in the repo, that file is all a guided agent needs to know where the run stands.

## Getting the tools (do this first)

This skill needs its own files (`scripts/`, `template/`, `docs/`); the README's install
(a clone) brings them. If `scripts/tools/1-2-baseline/split_asm.py` is not next to this file,
only `SKILL.md` was installed: fetch the tools yourself, without asking (they are this skill's own
public code, not third-party material), into a tools folder (default `~/dc-tools`). The tools folder always has to be
the latest version: clone it when it is absent, and when it exists update it (`git -C ~/dc-tools/dc-decomp-kickoff
pull --ff-only`; if that fails, delete the folder and clone again).

```
git clone https://github.com/consolesplayingconsoles/dc-decomp-kickoff ~/dc-tools/dc-decomp-kickoff
```

Then say one short line, "Tools ready: <version>" (the content of its `VERSION` file, or `git describe --tags --always`),
with no advice on how the user could avoid it: they cannot.

Then use that copy for every `scripts/...`, `template/...` and `docs/...` path below. Do not
rewrite the tools from this text unless the clone is impossible: they encode fixes that are easy to
get wrong (multi-track discs, link address, regex blowups, linker quirks).

## Requirements and the machine

**Requirements: Docker and Python 3, on any OS (Mac, Windows, Linux).** Docker is the default:
Ghidra and the Hitachi tools run in containers, so nothing else is installed. Only if Docker is
impossible and the machine is **Linux x86_64**: `DC_LOCAL=1` (opt-in, never a default) runs the
Hitachi tools through `wibo` on PATH and Ghidra from `GHIDRA_INSTALL_DIR` (Ghidra 12.x + JDK 21).
`DC_LOCAL` does not work on macOS or Windows (`wibo` is a Linux program): there, install Docker.
**In a cloud workspace** (a Claude conversation's own Linux machine) images often cannot be pulled,
and there is no Docker: use `DC_LOCAL=1` for every script. Install what it needs with
`bash scripts/tools/1-2-baseline/setup/setup_tools.sh --check` (reports what is missing, installs nothing), then
`bash scripts/tools/1-2-baseline/setup/setup_tools.sh` (wibo, unshield, JDK 21, Ghidra: pinned and checksummed, one step per line),
then `source` the `env.sh` the script prints (`~/dc-tools/env.sh` by default) in every shell that runs a script. The user's disc and SDK are in a folder of
that machine (ask for the folder); the repo is built there, so offer to hand it back to them at the end.

**Before starting, check the machine:**
- `python3 --version` works and is 3.6 or newer (on macOS, `python3` can be Apple's stub that
  opens an install dialog: then use another Python, e.g. from python.org or Homebrew).
- `docker info` works (no Docker on Linux x86_64: `bash scripts/tools/1-2-baseline/setup/setup_tools.sh --check`, then install, as above). Docker Desktop and colima share **only your home folder** with containers
  by default: keep the work folder, the repo and the SDK under your home folder, or mounts arrive
  empty (a build that "can't find" files it plainly has is this).
- About 4 GB free (Docker images ~1.5 GB, the SDK, the disc copy for the game image).

**The user brings the SDK and the game image, each as a folder they pick.**
Ask for the game image's folder and then for the SDK's: a path to a directory on the machine
the work runs on, never a download or an upload. Never fetch an SDK yourself, and never offer to. Never
search, list or browse the user's folders to find either one: ask and wait.

**The SDK folder can have any layout** (`bin/ shc/ shinobi/` as the disc images lay it out, or a
tree with `.../Utl/Dev/Hitachi` and `Lib`): scripts find `asmsh.exe`, `lbr.exe`, `lnk.exe` and the
`.lib` files by name. Point `SDK_PATH` at the SDK's top folder (quote it when it has spaces).

**A second SDK, optional: 1.55J (1999), for more names.** List it
to the user by its disc names and ask them to provide the images themselves; never download it:
"Dreamcast SDK (Sega Library) Ver.1.55J" **Vol.1 (Common Disc)** and **Vol.2 (For SHC Users)**
(Redump discs 87866 and 87867; Vol.3, CodeWarrior, is not needed). Lay it out with
`python3 scripts/tools/1-2-baseline/setup/sdk_from_iso.py <out folder> <Vol.1 .iso> <Vol.2 .iso>`: it checks each image
against its Redump record, then copies `bin/` (Vol.1) and `shc/` + `shinobi/` (Vol.2), about a second.
Without it everything below still works, with fewer names.

**Run the Ghidra actions one at a time.** Each needs ~1 GB; Docker Desktop and colima often default to
2 GB, so two at once get killed ("Killed" in the log). `sdk_sigs.sh` switches to one library per run
when Docker has under 4 GB. **Every script fails loudly**: never continue past an empty table.
Ghidra projects are the costly part: `DC_GHIDRA_PROJECTS=<folder>` keeps them there instead of in
the output folder, so cleaning outputs never wipes them (ask the user where, if they have a place).

**Long actions print progress** (Ghidra analysis ~3 min, first build a few minutes, textures a
minute or two): tell the user what is running and roughly how long before starting each.

**Evidence:** what the skill did on each game it has been run on (numbers, what broke, what
changed) is in `docs/evidence.md`; the sections below state rules, not games. Everything the
skill uses is in its own folder.

## Run it one action at a time

Never present several questions in one message. Do one action, say what it is and roughly how long it takes, run it, show its result, 
then go to the next. One question per message, asked when its action comes: new decomp or upgrade, then the game image's folder, then
(only when a tool is missing) the install, action by action, then the SDK's folder once `sdk_scan.py` has named
the release, then each optional extra as its action reaches it. A missing tool is installed or reported at
the moment it is needed, one tool at a time, never as a list handed to the user.

Say what an action is and why it exists, in one line. When an action repeats an earlier one (the second Ghidra pass, a rebuild), say
that it is planned and what it adds. When it finishes, give the number it produced (coverage before and after, counts,
sizes), not just "done".

Never go from one long action straight into the next. When an action finishes (an install, the Ghidra analysis, a build), say
in a line what finished and how long it took, then what comes next and about how long that takes, and only then start it.
While a long action runs, run it detached with its own log, its input closed (`</dev/null`) and a time limit that fits it (a few times the action's usual duration, in
minutes: these actions are long), and give a line of state when the user asks: a message from the user interrupts a command that is still running, and then nothing
comes back. If a command comes back interrupted or rejected, say so plainly, and look at the log before saying why and
before running anything again.

**Every action has a log, and every message about it gives that log.** Each action (a script, a build, a generator band, a queue of
them) writes to a log file of its own. The message that starts it, and every later message about it (its state, its progress, its
result), names the log's full path and a `tail -f` command for it, so the user can follow it without asking.

Every question with a closed set of answers is a real multiple-choice question (the client's question tool,
`AskUserQuestion` in Claude Code), the recommended answer first: new or upgrade, which release
when several fit, each optional extra (provide it, or skip), continue or stop at a decision point. Ask for a folder by its path. A client with no question tool gets the options as a numbered
list and is asked for the number.

## Third-party sources

The procedure needs two kinds of material (a Katana SDK and the game's disc), both brought by the user as the folder that holds them; the rest is optional. The sources below are identified solely as
examples of where optional material has been seen, as search terms for the user: this skill never fetches an SDK. The authors of this skill have no affiliation with, and
make no representation regarding, those repositories, their contents, or their licensing. Nothing
is retrieved without the user's express confirmation. The user is solely responsible for
determining whether they are entitled to obtain and use any such material, and may substitute any
equivalent material lawfully in their possession.

| need                                                                                                                                                                                                                                                                                           | where it has been seen (search terms; the user brings SDKs)                                                                                                                                                                                                                                                                          | used for                                                                                                                                                                                                                                                                                    |
|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Katana SDK (libraries + Hitachi `asmsh`, `shc`, `lnk`, `lbr`, `elf2bin`)                                                                                                                                                                                                                       | any Katana SDK release, installed or as a disc image (the one this skill's tests build with: R10.1)                                                                                                                                                                                                                                  | SDK signatures, the matching build                                                                                                                                                                                                                                                          |
| other Katana SDK releases, optional (disc images: 0.20 Pre 7 to R11b, 1.55J Vol.1 + Vol.2, Network 1.04; Katana 0.40 Release.4 for 1998 games; R1.42J and 2.00J come as InstallShield 3 installers, `is3_extract.py`; R2 and 0.20 Pre 7 carry GNU `ar` libraries this skill does not hash yet) | archive.org item `official-katana-sdks` (`OFFICIAL KATANA SDKs.zip`, one image per release); 1.55J is also catalogued by Redump (discs 87866, 87867); 0.40 and the Shinobi/Kamui library sources from sega-dreamcast-info.com's SDK archive page (https://www.sega-dreamcast-info.com/en/dreamcast-develppement-sdk-library-archive) | the release the game was built with (step 2), more SDK names                                                                                                                                                                                                                                |
| the Shinobi and Kamui library sources, optional                                                                                                                                                                                                                                                | sega-dreamcast-info.com ("The source code of the Dreamcast Shinobi/Kamui development library")                                                                                                                                                                                                                                       | exact C and names for the SDK part of every game: reference source for the C loop, their bundled `.LIB` files are one more signature table, and the Shinobi dump's `.LST` listings name statics (`sdk_masked.py --listings`)                                                                |
| the Sega NAOMI SDK, optional (for games built on the NAOMI library: arcade ports with `nl*` functions)                                                                                                                                                                                         | archive.org item `NaomiSDK` ("Sega Naomi SDK 001002": `archive/naomi/libwin.zip`, `libsgi.tgz`, `smpwin1-7.zip`, `doc.tgz`)                                                                                                                                                                                                          | the `nl*` / `nla*` / `nlsnd*` library (math, matrices, textures, sprites, print): one more signature table (`sdk_sigs.sh`, with a Katana SDK's `lbr.exe`/`lnk.exe` beside the libraries), its sample programs (`t.map` + `t.mot`) as another, and the API pages as each function's contract |
| cheat codes, optional                                                                                                                                                                                                                                                                          | gamehacking.org (per-game pages, public); the Dreamcast-Talk compiled CodeBreaker list (members' attachment, credits its code authors); the community's widescreen code lists                                                                                                                                                        | named variables (`scripts/tools/4-boosts/cheat_leads.py`)                                                                                                                                                                                                                                                  |
| a later port, a prototype, other decomps, optional                                                                                                                                                                                                                                             | the user's own copies (ports and prototypes), GitHub, hiddenpalace.org, tcrf.net, segaretro.org                                                                                                                                                                                                                                      | step 4                                                                                                                                                                                                                                                                                      |
| an older SDK, optional                                                                                                                                                                                                                                                                         | archive.org item `dcsdk-9e` (SDK R9 Europe, Nov 1999, disc 1: SHC 5.1 Release 08)                                                                                                                                                                                                                                                    | a period compiler for games built in 1999-2000; so far it gave the same bytes as R10.1's (Release 11)                                                                                                                                                                                       |

Ask before fetching anything from them (never an SDK). Never commit the SDK, the game's files, or anything that carries their bytes or
text (assembly, hash tables, the text map) to the new repo: its `.gitignore` already excludes them. What only
describes them (addresses, offsets, sizes, names: `functions.txt`, `globals.txt`, `models.txt`, `model-map/`) is
committed: the repo shares as much as is safe.

## New decomp or upgrade (ask first)

Before anything else, ask the user one question: start a new decomp, or upgrade one this skill
started? Ask it as a real multiple-choice question (the client's question tool, `AskUserQuestion` in Claude Code) with two options, "New decomp" (recommended, first) and "Upgrade an existing decomp"; plain text only when
there is no such tool. For an upgrade, ask for the repo's folder, then follow `docs/upgrade.md` (it asks for
the target version: the latest tag recommended, `main` offered as the dev version, never recommended) and skip the
procedure below.

## Procedure

The ten steps, in order. Each one is announced and closed as the section above says.

### Step 1: Decomp project setup

- **Name the conversation after the game.** As soon as IP.BIN gives the title (step 1), rename
   the session if your client lets you (e.g. "Dreamcast decomp kick-off: <title>"), so a user
   running several games can tell the conversations apart.
- **Disc to executable.** Ask the user for the path of the folder that holds the game image (a `.gdi` with its track files: only `.gdi` is supported). Never ask them to attach or upload files, and never explain how to set up the client. (`scripts/tools/1-2-baseline/gdi_read.py`). Check the
   boot file in IP.BIN; `0WINCEOS.BIN` means Windows CE: stop, this skill does not apply.
   **Check it is the game before splitting.** Look for the game's own text (menus, item or place
   names) in the executable. A big `.BIN` next to the boot file can be a bundled application
   instead (a web browser shipped for online registration: `http` strings, a perfect SDK match and
   none of the game's text). A boot file with none of the game's text may only be a core that
   loads the game's code at runtime from other files (relocatable modules): this skill handles one
   executable at a fixed address, so stop and say so (`docs/evidence.md` has an example).
- **Base and fingerprint**: `scripts/tools/1-2-baseline/setup/linkbase.py`, `scripts/tools/1-2-baseline/setup/banners.py`. Note the SDK version the game used.
   **Which SDK to ask for:** `python3 scripts/tools/1-2-baseline/setup/sdk_scan.py docs/sdk-banners.tsv <1ST_READ.BIN>`
   (`docs/sdk-releases.md` lists every release with the file names it has been seen under, as
   search terms for the user)
   ranks the publicly preserved Katana releases by how many of the game's library builds they
   contain. A full match: ask the user for the path of the folder where they keep that release, and only that. The
   SDK's library sources are asked for in step 5, and the other extras in step 4. None: say the game was built with a
   release not in the list, and to pick a close one; suggest the one or two the script names. If
   the user already has several SDKs, they can instead point at one folder holding all of them
   (images, zips or folders) and run `sdk_scan.py <that folder> <1ST_READ.BIN>`. Older releases
   ship inside InstallShield cabinets: `scripts/tools/1-2-baseline/setup/sdk_unpack.sh <image> <out>` lays any of them out
   as plain files (Docker, any OS) before `sdk_sigs.sh`. The 1998-1999 releases (R1.42J, 2.00J)
   are InstallShield 3 self-extractors instead: `python3 scripts/tools/1-2-baseline/setup/is3_extract.py <SETUP.EXE> <out>`
   (stdlib) unpacks every archive inside. Some discs also carry a samples zip with prebuilt
   sample programs and their link maps: those link the release's libraries, so hashing them
   (ELFs in `elf/`, `map_names.py` output in `names/`, then `ExportSigs.java` in folder mode as
   `sdk_sigs.sh` does) is a signature table too, with no installer to unpack.
- **The repo: ask the user where to put it.** Suggest a default (a sibling of the current folder,
   named from the IP.BIN title: lowercase, spaces to hyphens, plus `-decomp`, e.g.
   `SOME GAME` -> `<parent>/some-game-decomp`), always written as an **absolute path**. Create it,
   then confirm the resolved absolute path back to the user in one line. From here on, every path
   you show (commands, summaries, the final report) is absolute: never `cd <name>` alone.

### Step 2: Signature-driven baseline

- **Ghidra** (Docker; no Linux machine needed, the image builds on first use), with the
   executable in `<work>`:
   ```
   scripts/tools/1-2-baseline/setup/ghidra/dghidra.sh <work> /work proj -import /work/1ST_READ.BIN -overwrite \
     -loader BinaryLoader -loader-baseAddr <base> -processor SuperH4:LE:32:default \
     -scriptPath /scripts -preScript DcPre.java -postScript DcReport.java /work/report.txt
   ```
   Import at the base `linkbase.py` picked: at the wrong one Ghidra finds a fraction of the code.
   Never copy the `.java` scripts into `<work>`: Ghidra then finds two copies and fails to load them.
   **How much it finds:** compare the bytes inside functions with the executable's size. A game is
   often mostly data (models, tables), so a third can be normal; a whole region with `rts`
   instructions and no functions is code the analysis never reached. `scripts/tools/1-2-baseline/seed_funcs.py`
   lists function starts in uncovered stretches; re-import with `-preScript SeedFuncs.java
   <seeds.txt>` after `DcPre.java` so the analysis follows them. Code reached only through switch
   tables (`braf` / `jmp @Rn` with a table of offsets) or runs of function pointers stays hidden
   to both: read those tables when a region still looks like unreached code.
- **Names**:
   - SDK-wide: `scripts/tools/1-2-baseline/setup/sdk_sigs.sh <SDK folder> <out>` -> `<out>/katana-sdk.sigs`. Any SDK layout:
     the Hitachi tools and the `.lib` files are found by name. Build once per SDK and keep the table
     beside the SDK folders (not in a scratch dir): it is minutes to an hour of hashing to rebuild.
     Details and gotchas: `docs/sdk-signatures.md`.
     With the 1.55J folder too, run it again into a second folder (`<out155>/katana-sdk.sigs`) and
     apply both tables.
   - **Apply every table you have, all in one Ghidra run**, then `DcReport.java`:
     all the SDK tables merged into one (`cat` them into one file), with `ApplySigs.java <sigs>
     <out> apply`: a hash that two releases name differently stays ambiguous, so twin stubs
     (byte-identical code under unrelated names) are never named by which release has which.
     Only unique matches are applied; the same tables always give the same names. A unique match
     on a tiny function (a few instructions) can still be a collision with unrelated library code:
     report short names that make no sense where they sit (a video-player function in a game that
     plays no video) as suspect, never silently trust them.
   - **Types from the SDK's headers**, once the names are in: `scripts/tools/1-2-baseline/setup/sdk_headers.py <SDK folder>
     <out>` copies the headers in a form Ghidra's C parser reads, then, in the same Ghidra run as
     `DcReport.java` or on its own, `ApplyHeaders.java <out>/shinobi/include
     <out>/shinobi/include/SHC <out>/shc/include <out>/stub -D__SHC__ -D_SH4`. It parses the
     release's headers into the program (R10.1: 2,372 prototypes, 423 structs such as
     `PDS_PERIPHERAL`, `NJS_OBJECT`, `KMVERTEX`), gives every named function that has a public
     prototype its real signature, and types the literal-pool words SH-4 calls through, so the
     decompiler shows `PDS_PERIPHERAL *` where it showed `undefined4`. Only the public API gets
     a prototype (one named function in five: the rest are library internals); use the headers
     of the release `sdk_scan.py` picked.
   **Split**: `scripts/tools/1-2-baseline/split_asm.py <1ST_READ.BIN> <base> <report> <repo>`: one `.src` per function,
   data words, exported labels, `objects.txt` in link order.
- **Make the repo publishable and build it.** A pushed repo holds no game bytes, so it must be
   able to regenerate them from each user's own disc. Into the repo:
   - copy `template/` (`build.sh`, `setup.sh`, `disc.sh`, `textures.sh`, `Makefile`, `models.txt`, `symbols.txt`, `README.md`, `AGENTS.md`, `KICKOFF`, `status.txt`, `port/` (the native port's runtime, experimental: its README)),
     and `template/gitignore` as **`.gitignore`** (shipped without the dot: some installs drop
     dotfiles);
   - copy `scripts/tools/` whole as **`tools/`** (without `__pycache__` and without `1-2-baseline/setup/`, the kickoff's own
     scripts, which run from this skill before the repo exists): one folder per step (`1-2-baseline/` to `8-build/`,
     each with a README of its tools), `sim/` (the simulator, its checker and the disassembler), `common/` (the tools many
     steps share), and at the top `progress.py` and `toolpath.py` (every folder on the import
     path), `hooks/` and `tools-image/` (so a cloned repo builds its own tools image, nothing pulled from anyone else).
     The repo's `tools/` and this folder stay identical: a tool changes here first;
   - write `sdk.txt`: `scripts/tools/1-2-baseline/sdk_txt.py <repo>/functions.txt <base> <1ST_READ.BIN>
     <SDK ApplySigs output>`. It marks the boot block
     and the SDK library block;
   - write the base to `BASE` (hex, no `0x`); `split_asm.py` already wrote `functions.txt`;
   - fill the placeholders: in `setup.sh` and `disc.sh` `@BOOT@` (boot file from IP.BIN) and `@SHA1@` (of that
     file); in `README.md` `@TITLE@`, `@RELEASE@` (IP.BIN: title, product number, version, date,
     region), `@BOOT@`, `@SIZE@` (with thousands separators: `1,477,040`), `@SHA1@`, `@BASE@`, `@SDK@` (main banners), `@FUNCS@`, `@NAMED@`,
     `@NAMED_SDK@`, `@SKILL_VERSION@` (the skill version the repo came from: `v0.5` for a tagged release,
     `v0.5+1a2b3c4` for a dev version, the commit `1a2b3c4` after tag `v0.5`; in a git checkout it is
     `git describe --tags --exact-match` if that succeeds, otherwise the last tag + `+` + the short commit;
     without git, the content of this skill's `VERSION` file (the last release); also in
     `KICKOFF`, the version an upgrade starts from: `docs/upgrade.md`), and `@PROGRESS@` (after the first `MATCH`: the
     output of `python3 tools/progress.py` in a ``` fence). No `@...@` may remain in those files
     (`grep -n '@[A-Z_]*@' README.md setup.sh disc.sh Makefile KICKOFF`; `tools/` has its own `@N@` tokens, ignore).
     In `README.md` keep the `<!-- MODE: ... -->` block for the repo's mode (`status.txt`'s `MODE` line; none: equivalent) and
     delete the other block; then delete the marker lines of the one kept (`grep -n 'MODE:' README.md` finds nothing).
     `@NAMED@` = functions whose name is not `FUN_...` (what `split_asm.py` prints). It can exceed
     `@NAMED_SDK@`: small wrappers (thunks) inherit the name of what they call.
   - **no licence**: the repo gets no `LICENSE` file and no licence section. Its contents derive
     from the game's own code, whose rights are the publisher's: claiming ownership or granting
     others rights would overreach, and default copyright says nothing more than it should.
   - `chmod +x build.sh setup.sh tools/hooks/pre-commit` (tell the user; it is one command).
   - the pre-commit hook (`tools/hooks/pre-commit`, from `scripts/tools/hooks/`) does two things on every commit: it keeps the README's
     Progress block current, and it runs two quick checks (retcheck, and the audit of `tests/equivalent.txt`; `SKIP_COMMIT_CHECKS=1` skips them). It also refuses a commit with a staged file over 50 MB (`PRE_COMMIT_MAX_MB`) or when `progress.py` fails. It does not
     build, and it does not prove the staged sources again: each function was proven when its C was written, and checking every staged file again cost about a
     minute a file (Virtua Tennis, 297 files: about five hours). Enable it with `git config core.hooksPath tools/hooks`.
   - write `.env` in the repo with `SDK_PATH="<absolute SDK folder>"` (gitignored, machine-local),
     so the user can rebuild with a plain `bash build.sh` later.
   Then put the original executable in as `1ST_READ.BIN` and run `bash build.sh`. It must print `MATCH`. First run assembles every file (minutes); later runs only
   changed ones. Always invoke scripts with `bash`/`python3`: downloads can lose execute bits.
   Finally prove the published layout works: empty `asm/`, `objects.txt`, `text-map/`, then
   `bash setup.sh <disc.gdi>` and `bash build.sh` again: `MATCH` again.
   Then the masked SDK pass, with every table folder from the names above (and, with the Shinobi or
   Kamui source dump, `--listings <dump folder>`): `python3 scripts/tools/1-2-baseline/sdk_masked.py <repo>
   <repo>/1ST_READ.BIN <table folder>... [--listings <folder>] --apply`, then `split_asm.py`
   and `bash build.sh` (`MATCH`). It names library code the hashes missed (internal library
   builds, twin stubs, statics, starts the split missed; `docs/sdk-signatures.md`).
   Then `python3 tools/1-2-baseline/missed_funcs.py 1ST_READ.BIN <base> functions.txt`: code the analysis did
   not make into functions (callbacks reached only through tables, getters only through literal
   pools, state handlers merged into a neighbour, whole functions in a big gap when something
   points at an entry). Expect hundreds, about half backed by a pointer. They matter for C units, whose ends must be function boundaries. Report the count
   and leave the list for review: adding an entry never changes the bytes (still `MATCH`), only
   `python3 tools/progress.py` gives the starting state.
   Then the routines listed code reaches or hands on: `python3 tools/common/boundaries.py --discover --values > candidates.txt`
   (what it jumps or calls to, and the code addresses in pool words it loads and passes on: callbacks, state handlers), then
   `python3 tools/common/boundaries.py candidates.txt` (the plan: each candidate checked, data refused) and `--apply`, `split_asm.py`,
   `bash build.sh` (`MATCH`). Run it twice: a routine named only by another unlisted one shows in the second round. Without the
   values, Jet Set Radio's 830 such routines (151 KB) stayed unlisted until the build from C (step 8) refused to hand on their addresses;
   from the executable alone the first round names 816 of them.
   Then `python3 tools/1-2-baseline/checksizes.py --extend --write`, `split_asm.py` and `bash build.sh` (`MATCH`): the analysis
   ends a function at a literal pool in the middle of its body, and a size shorter than the code makes every case of that function
   run to the simulator's step cap (Virtua Tennis: 49 generator timeouts, ~600 short sizes; `tests/checksizes`).
- **Game build**: `bash disc.sh <original .gdi>` writes `build/disc/`: a copy of the user's disc
   with the rebuilt executable and every file under `disc/` (same path as on the disc) written in
   place, error correction recomputed, read back to verify. A smaller file is padded; a **bigger**
   one moves into free sectors (GD-ROMs often carry a whole filler track) and its directory entry is
   repointed. To change the executable from a modified copy, `tools/1-2-baseline/apply_bin.py <repo> <original>
   <modified>` writes the changes into the asm data words; then `bash build.sh` (it prints DIFFERS,
   expected; `DC_EXPECT_CHANGES=1` makes that exit 0).

### Step 3: Asset mapping

- **Asset maps**: all of them, with no question to answer. **Text map** (for translators, English included: any language can be a source as well as a
   target): `scripts/tools/3-assets/text_map.py <1ST_READ.BIN> <base> <repo>/text-map <disc.gdi> [tier]`.
   - `exe_strings.tsv`: every executable string: address, offset, encoding, length and text.
   - `files.tsv`: text density per disc file.
   - **Text files:** the skill detects nothing here. A decomp lists its text files in `models.txt` (`text <disc path>`, one per line, the path as in `files.tsv`) and `setup.sh` runs `scripts/tools/3-assets/text_dump.py`, which copies exactly those files, as they are, into `text-dump/` (git-ignored: it holds the game's text). Shuriken's Text tab shows that folder, a page of lines at a time.
   - `images.tsv`: every disc file that holds images (PVR textures found in it, or an image file extension). It
     makes no guess about text in images: that is for a person to see, on the contact sheet below.
   - Textures are their **own step** (`bash textures.sh <disc.gdi>`, seconds to a minute): every
     standard (PVR) texture decoded to PNG on one page with checkboxes (`text-map/textures/`), for a
     person to look through. A game that keeps its art in its own formats gets 0 here and a
     note saying so; its textures are then in the model map's `[textures]` section, if it has one.
   - **Model map** (`scripts/tools/3-assets/model_map.py <1ST_READ.BIN> <base> <report> <disc.gdi> <repo>/model-map
     [<repo>/models.txt]`): every NAOMI-library model in the disc files (records that parse exactly), the
     address each file is loaded at (found by matching the executable's pointers to the models' starts, no
     profile needed), every pointer to a model followed back to its table, and the table named by a rule in
     `models.txt` (curated: characters, cars, a skeleton, a texture list), a data symbol, or the functions
     that use it. One file, `model-map/game.dcgs`: sections `[models]`, `[assemblies]`, `[rigs]`, `[bones]`, `[motions]`, `[images]`, `[audio]`, `[textures]`, tab-separated; its first line `# dcgs <version>` is the skill version (`KICKOFF`).
     **It is committed, unlike `text-map/`**: only the game's text and bytes are kept out of git, and this file holds
     addresses, offsets, sizes, our names and one standing pose's matrices, no bytes and no text.
     `models.txt` starts as only its syntax comments; fill it from the notes as tables are understood. A game
     whose models are in another format lists none here, and the step says so. Texture lists matter: the
     texture's real size, type and format come from the game's own list, not the model records.
   - **Audio** (the `[audio]` section of the same file): every CRI ADX / AHX stream the disc holds, inside AFS archives or
     on its own, found by its header, with channels, sample rate, samples and seconds; a DTPK sound pack inside an AFS archive is
     opened and gives one row per sample (index = entry * 10000 + sample; the rate is nominal, the pack records none),
     a loose DTPK sound bank is listed as a bank. An AFS archive counts only when at least one entry is audio (a city or model archive is skipped). The
     archives carry no entry names, so a sound is `FILE:index`, named by a `sound <file> <entry> <name>` rule in `models.txt`.
   - `setup.sh` rebuilds the text map from `functions.txt`, so a cloned repo's `files.tsv` lists
     function-level users only; the kick-off's own run (from the full Ghidra report) has more.
   - Tiers: `quick` = executable only (seconds); `standard` = plus a 2 MiB sample of every disc file
     (seconds to a minute); `deep` = whole files (minutes on a full disc).
   - Density and the Shift-JIS count are counts, not a verdict: binary data scores as text sometimes.
   - **OCR is not included, on purpose.** Finding baked text in single-language games would mean
     decoding every texture (PVR, often thousands per disc) and running OCR on each: tens of
     minutes to hours, plus an OCR engine and its Japanese data, and game fonts are stylised, so it
     misses text and flags noise. If a user wants it, warn them of that cost first. A contact sheet
     of all textures, looked at by a person, is the method this skill provides.

The maps open in [Shuriken Explorer](https://github.com/consolesplayingconsoles/dc-shuriken-explorer), which reads them to show the game's models, textures, sounds and text.

### Step 4: Opportunity-driven optional boosts

- **Extra material: ask the user, one short form.** Open with: "These are optional; the
   kick-off works without them, but each one saves work in every step after it, the earlier the better. Not all games have a later
   port or a prototype, but where they do, providing them is encouraged, as they can be the strongest source of information
   available." Then
   ask these as separate questions (a form where the client has one, a numbered list otherwise),
   each answered with a folder or file, a link, or "no". Most likely first:
   1. **Cheat codes for this game** (a saved code list in CodeBreaker/Xploder format, or a saved
      gamehacking.org page). Every code is an address with a meaning: named variables. Widescreen
      codes count too (the community's CodeBreaker/hex widescreen hacks, one or two codes per
      game): each is the game's projection or aspect value, a named global.
   2. **Other regions or revisions of the game.** Same code: names and addresses carry across.
   3. **Existing reverse-engineering notes or a partial decomp** (a repo, thread or wiki page).
      Reference names and pitfalls.
   4. **A later port** (Android `.apk`, iOS, PC, another console). The big one when it kept its
      symbol table: it can name a large share of the functions and globals.
   5. **A decomp of the same game on another console.** Structures, class names and logic;
      no bytes match.
   6. **A prototype, debug build or dev kit dump.** Pre-release discs sometimes carry the
      linker's `.ELF` or `.MAP`, or a build log inside a data file, with every name; a studio's
      dev kit dump can hold the project folder with its link maps, ELFs with debug info
      (`scripts/tools/4-boosts/elf_debug_names.py`) and source. Whether one exists for the game:
      https://www.sega-dreamcast-info.com/en/releases-prototypes-sega-dreamcast-iso (about 300
      Dreamcast prototypes and the published dev kit dumps, with what each one holds) and Hidden
      Palace's Dreamcast list (https://hiddenpalace.org/Prototypes_by_system/Dreamcast). With no ELF or map, still diff
      its strings against the release: debug readouts and menus left in early builds carry their
      own labels (`printf("Act    = %d", ...)` names the field it prints).
   7. **A sibling decomp** (same team: games that link the same in-house library, an engine or maths layer no SDK table knows).
      An offer, never a search: work only with a repo whose path the user gives you, and never look through their other folders for one.
   Record each answer in the game's evidence entry. Only 1, 4, 6 and 7 feed a tool: 1 ->
   `scripts/tools/4-boosts/cheat_leads.py` (globals candidates, below); 4 -> `docs/port-symbols.md`,
   symbols check first; 6 -> a symbol scan before anything else, then the strings diff; 7 -> `scripts/tools/4-boosts/sibling_names.py`. 2, 3 and
   5 become references in the repo's docs, and names only when the source is itself a matching
   decomp (`ExportSigs.java`).
   Never go looking for any of it: use what the user gives (a path, or a link they provide, which you may read). Never fetch
   games, SDKs or any extra that contains IP (a later port, a prototype, other regions): the user supplies those as paths.
   - **Cheat codes** (when the user gave a list): `scripts/tools/4-boosts/cheat_leads.py <list.txt> <title>
     <1ST_READ.BIN> <base>` prints one line per code: address, size, write or compare, the
     cheat's name. Those are globals candidates with their meaning (health, timer, cash...). Most
     are RAM variables beyond the executable. A list for another region of the game names the
     same variables at other addresses, and not by one constant shift (one build moved its game
     state block by 0x22E0 and its option flags by 0x2358): find each by its use in the code
     before applying it. `cheat_leads.py fetch <title>` takes the list from libretro-database.
   - **Sibling decomp** (when the user gave a path): `python3 scripts/tools/4-boosts/sibling_names.py <sibling repo> <repo>` proposes its names for exact
     masked matches that are unique both ways and lists the twins; `--apply`, then `split_asm.py` and `bash build.sh` (`MATCH`).
   - **A later port, a prototype**: as above (`docs/port-symbols.md`; the symbol scan), then `split_asm.py` and `bash build.sh` (`MATCH`).
   - End the step with `python3 tools/progress.py`: the names the extras added.

### Step 5: Incremental script-generated decomp

- **Matching mode.** In a project with `MODE: matching` (`status.txt`) this step is matching C, one original source file at a time: `docs/matching-c.md`, `docs/matching-units.md`. The bullets below are the Equivalent mode's.
- **Library sources (optional).** Ask the user for the Shinobi or Kamui library source dump (a path, or "no"). With it:
  `python3 tools/5-generated/sdk_source.py <source folder>...` in the repo. It
   compiles them with the SDK's own shc and keeps every function whose bytes they reproduce: the exact C goes to
   `sdk-source/` (git-ignored), the names to `sdk-verified.txt`, and `progress.py` counts them in. Tell the user
   what it wrote, and that `sdk-source/` is the SDK's own code: adding it to the repo is their choice.
   Report its `suspect` lines as such. Count `@NAMED@` and `@NAMED_SDK@` after it.
- **Generated C.** `python3 tools/5-generated/gen_equiv` writes Equivalent C for the functions that need no thinking, checked against the original in the SH-4 simulator.
  Report it apart from hand-written C. A function that passes is done; there is no coverage pass mark, and the total test coverage is the quality figure.
  A draw has a time limit (`max(60, size/8)` s times `GEN_TIME_FACTOR`). It is CPU time, not load: a small function with big call answers
  can need minutes. The first pass keeps the short limit, so one function that really hangs cannot hold a run; the run ends by printing the
  second pass for the functions that timed out, and only those: `GEN_TIME_FACTOR=8 python3 tools/5-generated/gen_equiv --jobs 1 <size> <names>`,
  smallest first, alone on the machine (`tools/5-generated/gen_equiv/secondpass.py`, `tests/test_gen_secondpass.py`).
- **Polish.** `python3 tools/5-generated/gen_equiv --direct` / `--retest` widen the cases, guided by how much of the original they run, and list functions whose C fails on them.
- **Do not lose work.** `state/kept` and `gen_equiv --recheck` keep and re-check what failed; `tools/common/consistency.py --fix` after overlapping runs; run in byte batches (`GEN_BATCH`); `tools/5-generated/remaining.py --table` shows where every function stands.
- **The SDK's C in its own folder.** The generator writes into `src/`, which is the game's own code. A function inside a library block of `sdk.txt` is the SDK's: its C belongs in `sdk/<library>/` (`sdk/shinobi/`, `sdk/kamui/`, `sdk/naomi/`, `sdk/sofdec/`, `sdk/runtime/`, `sdk/boot/`). `python3 tools/5-generated/sdk_place.py` prints the plan, `--fix` moves each file (or splits a file that mixes libraries, its cases following each function). Run it after each generator run, before the step's report.
- End the step with `python3 tools/progress.py` and the instruction coverage `equiv.py` reports.

### Step 6: Experience-driven agentic decomp

- **Matching C.** Matching C, one source file at a time, is also written here (`docs/matching-c.md`).
- **An outlier function is done in parts, never in one long run.** A function far larger than the rest (several KB, over every band's
  limit, or a timeout on its own) is not given a longer time limit or a bigger band: a whole run of it blocks the machine for hours and
  ends in a timeout. Instead:
  1. *Map it*: `python3 tools/6-agentic/parts.py map <name>` cuts it along its dominator tree (a block that dominates a region is
     entered only through its first instruction: a part), descending through chains with one big child until every part is at most
     600 instructions (`--max`); long `jmp`s through a pool word to one place are the sections' shared exit. Read the map against
     the disassembly: repeated sections of the same shape are one routine written several times.
  2. *Read each part*: `python3 tools/6-agentic/parts.py read <name>` lists every part as an entry of a scratch copy of the repo and
     has the generator read it as a small function (`state/parts/<name>/<part>.c`). What a part receives from the parts before it
     shows in its C: the parent's frame words as stack parameters, the callee-saved registers as temporaries read before they are set.
  3. *Join by hand*: one function, one frame (the original's, as an array), the parts in order, the exits the compiler shared between
     parts written once. Calls trimmed to their callees' definitions.
  4. *Prove the joined function* on drawn cases that reach every part, then directed cases (`--direct`) for what the drawn ones miss,
     at the coverage bar of step 7. The directed cases find the faults of the join.
  Seen on Virtua Tennis cameraExec (14.6 KB, twelve camera modes, one part per case: 155 cases, 4,940 of 5,627 instructions) and on
  Jet Set Radio FUN_8c0d296c (13 KB, no calls, eleven `jmp`s to one exit: a 10-instruction head, then four sections of the same
  shape, parts of 100-580 instructions). `docs/evidence.md` has both.
- **Hand over**: `template/AGENTS.md` is the loop and the steps; write the repo's plan into it (what is left, by pocket).
   **Print the run as an evidence entry** (the format at the top of `docs/evidence.md`:
   game, SDK by banners, counts, MATCH, text-map highlights, and what broke or surprised), and
   tell the user they can send it to the skill's repo as an issue so the next version learns from
   their game. Never write into the skill's own folder.
- **GitHub (optional)**: print, do not run, the commands for the user:

   ```
   cd "<absolute repo path>" && git init && git config core.hooksPath tools/hooks && git add -A && git commit -m "Kick off: byte-matching split, <n> named"
   # check first: git ls-files must show no asm/, 1ST_READ.BIN or other game files
   gh repo create <owner>/<repo dir name> --public --source . --push
   ```

### Step 7: Code size reduction

Starts when every function that can have C is proven. The goal: the code compiled from that C fits the space the original game
code had, so the build of step 8 leaves every other address of the executable where it was.

- **Measure** with `make c`: `prelim` links the C at one address twice, plain and through the optimizer (`build/cbuild/opt.json`),
  and `fit` says how many bytes are over (the literal pools and constants count, as in the build). It needs `layout.txt` (step 8,
  first point).
- **Shrink**: `python3 tools/7-reduction/shrink.py <name> ...` writes each function again and keeps the new C only when it is
  strictly smaller (`tools/7-reduction/sizes.py` measures both the same way) and still proven on its cases. Smallest functions first: they
  are cheap and add up; stop when the target and a little spare are reached. `--regen` keeps the new C at any size when it is
  proven, for after a generator fix. `tools/7-reduction/hoist.py` holds a value the original loaded once in a local.
- **Rewrite passes first**: `python3 tools/7-reduction/shrink.py --passes` rewrites the current C of every unit with the
  strategies that change no address or type (callees declared wider than their own definitions narrowed, with the leftover
  registers and frame words their calls passed dropped; frame slots stored back unchanged dropped; far field accesses as one-field
  structure members, frame slots held in locals, nearby globals reached off one base, a state chain of ifs on one variable as a
  switch, a result threaded up through nesting levels by `tA = (tB);` copies merged into one temporary, a pure builtin called repeatedly with the same variable computed once (`hoist`), the stack array based at its
  first used word (`rebase`), a stack array nothing reads dropped with its stores (`deadframe`); the sign sequence of a signed remainder by a power of two as `% 0x40` (`smod`); `gen_equiv/rewrites.py`), and keeps each
  function that compiles smaller and is still proven. No regeneration, so it is fast: run it before the regenerating shrink.
  Zombie Revenge, 80 random units: 28-38% less excess, 50% with `narrow`; on the medium units 25-41%; `rebase` ~4 bytes and `hoist` ~14 and `deadframe` ~17 per function they change.
  `tools/7-reduction/residue.py` lists the C shapes the bloated functions share and the fine ones lack: where the next pass comes from. The generator now ends every function with the same
  rewrites (`rewrites.py`: self-copies, struct access, global base, switch, copies, hoist, deadframe, rebase; `narrow_unit` on each unit it writes), so new C is born as
  small as the passes make old C. What only a person rewrites: an unrolled software-pipelined loop, flat
  register-level C, a join the structured form copied with renamed temporaries, switch cases differing only in constants.
- **One pass at a time**, and never edit the generator, the checker or the simulator while one runs: a pass stamps what it keeps
  with their hashes, and every later re-proof fails.
- **Outliers** (one function the generator gets wrong) are fixed in the C by hand, proven, and reported as a skill unit test
  (`tests/`), not patched into the tools.
- **Manual only**: C written by hand carries `/* manual: <reason> */` right above its definition; shrink.py, hoist.py and the
  generator's recheck and rebuild leave it alone (`tools/common/consistency.py manual_names`).
- **Coverage bar for any rewrite**: a rewrite of a proven function (a shrink pass, a regeneration or C written by hand) is accepted only when `equiv.py` proves it on cases that cover at least 70-80% of the function's instructions (the `N of M instructions` of its line; aim far higher), and the instructions left uncovered are not a whole branch; below that the old C stays. `equiv.py` calls a function Equivalent whatever its coverage, and `shrink.py` does not enforce the bar. Power Stone 2: a hand version passed at 12% with two bugs in it (an inverted compare, a pool float read as -6.0 for -24.0) and was caught only at 98%; a function's old C had passed with 0 of 574 instructions run. Raise coverage with `tools/6-agentic/fuzzcases.py`, `casesearch.py` or hand-written case JSON.

### Step 8: Build from C

- **Layout**: write `layout.txt` in the repo (`tools/common/layout.py`): `game` (the game's own code, required), `fill` (spare room in
  the file before it), `code` (what the cases may not write to), `spare` (unused RAM, test builds only). Read it off the RAM map:
  the boot code, the entry, the libraries, the data and the SDK stay where they are. **`game` is the game's own code only**: the
  library ranges of `sdk.txt` (SDK, NAOMI, the C runtime) and the data blocks stay outside it, as the original bytes, and are not
  compiled from the C by default. The SDK's C, where there is some, lives in `sdk/<library>/`: the console build compiles `src/` alone, a port builds from both. Building the SDK from C as well is possible, but it is not the default and needs work on the user's side. A `game` line that spans the whole executable rebuilds the libraries at the C's size for nothing: Virtua
  Tennis lost about 45 KB of its budget that way (SDK +27 KB, NAOMI and runtime +19 KB by function sizes) and spent a day
  shrinking code that should not have been in the build. The libraries are Sega's: a build takes them as the original bytes, or links them from
  the user's own SDK (bring your own SDK), never from C of ours. A library or data block in the middle of the game code is a `keep`
  region (it stays at its address; the words in it that point at moved game code are followed); a block at the end is where
  `game` ends. Before any shrinking, put the layout beside the one of a game that fits (Crazy Taxi: `game` 342 KB of game code,
  `fill` 49 KB, libraries outside) and account for every difference.
- **Build**: `make c` builds `build/cbuild/game.bin` from the C (`tools/8-build/cbuild.py`: copies of the C, pieces for what has
  no C, units of generated files compiled together, then `fit`: layout and link with Hitachi's inter-module optimizer, repeated
  with each part's measured ratio until the map shows every part inside its place). `asm-functions.txt` (one name a line) makes
  the build take those functions from the original asm although their C is proven: a test aid, empty in a real build. The image must have the original size; outside the game
  code only the pointer words to game functions may differ, each pointing at its function's new address. `make disc GDI="..."`
  writes a copy of the disc with it.
- **Checks before the build**: `make c` first runs `tools/8-build/retcheck.py`: every function's C must return in the register the
  original returns in (`sts fpul,r0` / `mov ...,r0` is r0, a write to `fr0` is fr0); a mismatch stops the build. The pre-commit hook
  runs it too. `cbuild.py` refuses a C call into the middle of another C function, naming the address and the C line.
- **Before the first build** (each one failed a build from C once; `docs/evidence.md` has the cases):
  1. Missed functions: step 2's `missed_funcs.py` has run (`missed.txt`) and its findings are in `functions.txt`; a repo
     that passed step 2 before the tool existed runs it now. Code it misses is built as a data table, its pools break.
     Functions listed this late go back through the steps after 2 like any other: step 5 draws them, the rest is step 6.
  2. Dropped arguments: no pass-through trampoline takes fewer arguments in C than `state/arity_scan.json` gives;
     regenerate them and their callers (`gen_equiv --regen`), fix by hand a caller that still drops them. An entry
     `"pass-through"` is a trampoline whose target is read from memory (a table jump): its arity is unknown, not zero, so
     list those too, regenerate their callers, and check each caller against the registers the original sets before the call.
  3. Undefined names: `cbuild.py` stops on them (the linker alone sends every such call to address 0).
  4. Stale references: after the link that fits, `cbuild.py` runs `tools/8-build/audit.py` and stops before the disc when a C
     number, a copied word or a table piece still points into the old game code, or a table piece holds code.

### Step 9: Runtime repairs

- **Run**: the user runs the disc on the console or an emulator and reports where it stops or what is wrong. Each stop is traced to
  one function and to the step whose output caused it (a function cut wrong in `functions.txt` from step 2, generated C or a
  declaration from step 5), and fixed there, proven again, built again. Nothing is guessed from the symptom: the frame it stops in,
  its call graph from the original, the built image against the original (stale addresses, second copies, result registers), then
  the one function. Flycast's GDB server (program counter samples, memory reads) is the last resort when reading does not settle it.
- **Known classes** (Crazy Taxi, 2026-10-24; `docs/evidence.md`): constants read from the original's literal pools by address
  (`tools/8-build/codeconsts.py --write` puts the values in); a C call into another function's middle from a wrong cut (`cbuild.py`
  refuses it); a result type declared on the wrong register (`tools/8-build/retcheck.py` refuses it).
- **Badge**: one badge, `badges/progress.svg`. The main metrics are large: covered functions and covered bytes; the secondary ones are small: test coverage and the matching percentage. Below them, a grid of four checks (BUILDS FROM C, BOOTS TO MENU, PLAYABLE, STABLE) in three columns, Flycast, Dreamcast and Native. `status.txt` in the repo lists the statuses in order: `[x] [x] [ ] BUILDS FROM C`, `[x] [ ] [ ] BOOTS TO MENU`, `[ ] [ ] [?] PLAYABLE`, `[?] [?] [?] STABLE`. A line with three marks is Flycast, Dreamcast, then Native and is on the badge (two marks, the older form, are Dreamcast and Native, Flycast not tested); a line with one mark is not. A column shows once its BUILDS FROM C is ticked: a target the game does not build for yet has none. `[x]` reached, `[ ]` tested and not reached, `[?]` not tested yet, shown as a question mark. Each needs the ones above it in its own column, and progress.py stops on a tick under an
  untick. The badge shows the grid from the first day.
  `status.txt` also says the repo's mode on a line of its own, `MODE: equivalent` (the default, also when the line is missing) or `MODE: matching`: in a matching project a function is done only when its C rebuilds byte for byte, `progress.py` reports "done: matching C" without test coverage, and the repo's `AGENTS.md` says which of its sections apply to each mode. Every layout or build option beyond the default is opt-in (a `+` option in a unit's header, `--overlay` on `build.sh`, the overlay report only when `overlays.tsv` exists): a repo that uses none of them builds and reports as it always did, and `tests/fillopts`, `tests/units` and `tests/progress_mode` guard that. `docs/matching-units.md` and `docs/overlays.md` describe them.

### Step 10: Native port

Runs the game on a host from the proven C, as an x86-64 Linux program (experimental). The repo's `port/` is the runtime: fill in `port/runtime/game.h` from `functions.txt` and `globals.txt`, build the container from `port/Dockerfile`, then build, extract the disc's files and run as `port/README.md` lists. The game on the console does not need the SDK decompiled: it stays the original bytes in the build, and the decomp is complete without it. For a port every SDK function needs C, except the hardware drivers (`sdk.txt`'s `hardware` lines), which the runtime replaces (the `SDK` rows of `progress.py` show how many functions have C). It needs nothing from steps 7 to 9, so it can start once enough functions are proven; what it finds goes back to steps 2, 5 and 6. It is reached when `status.txt`'s Native column ticks PLAYABLE: the game plays on the host.

## Rules

- The build must match before handing over, and after every change.
- Names are only applied on unique matches; ambiguous hashes are listed, never guessed.
- Link order is address order; a file's size never changes unless its replacement matches.

## Scripts

Grouped by the step that first needs them (scripts, then templates, then docs within each group).

### Tools for step 1: Decomp project setup

| script                               | what it does                                                                                                                                                                                                                                                                                     |
|--------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `scripts/tools/1-2-baseline/gdi_read.py`                | list / extract files from any data track of a GDI; extract IP.BIN                                                                                                                                                                                                                                |
| `scripts/tools/1-2-baseline/setup/linkbase.py`                | pick the import base from self-pointer counts                                                                                                                                                                                                                                                    |
| `scripts/tools/1-2-baseline/setup/banners.py`                 | SDK module banners: name, version, build date                                                                                                                                                                                                                                                    |
| `scripts/tools/1-2-baseline/setup/sdk_from_iso.py`            | SDK 1.55J folder from its Vol.1 + Vol.2 disc images, checked against Redump                                                                                                                                                                                                                      |
| `scripts/tools/1-2-baseline/setup/sdk_scan.py`                | which SDK release built the game: its library banners against `docs/sdk-banners.tsv` or a folder of SDKs                                                                                                                                                                                   |
| `scripts/tools/1-2-baseline/setup/is3_extract.py`             | InstallShield 3 installers (SETUP.EXE / .Z) as plain files: directory + PKWARE implode, stdlib                                                                                                                                                                                                   |
| `scripts/tools/1-2-baseline/setup/sdk_unpack.sh`              | any SDK image or zip as plain files, InstallShield cabinets unpacked (`unshield-image/`)                                                                                                                                                                                                         |
| `scripts/tools/1-2-baseline/setup/iso_extract.py`             | copy every file out of a disc image or zip (Joliet or ISO9660, no mounting)                                                                                                                                                                                                                      |
| `scripts/tools/common/docker_check.sh`            | Docker installed vs running vs low memory, and the tools image on first use                                                                                                                                                                                                                      |
| `scripts/tools/tools-image/Dockerfile`     | the `dc-tools` image: small Linux + pinned, checksum-verified wibo                                                                                                                                                                                                                               |
| `scripts/tools/1-2-baseline/overlay_scan.py`            | classifies every file of an extracted disc (SH-4 code, ARM code, sound bank, texture, data) and proves whether it holds SH-4 code (`python3 tools/1-2-baseline/overlay_scan.py <dir> [--md]`) |
| `docs/sdk-banners.tsv`         | library banners (module, version, build date) of every preserved Katana release                                                                                                                                                                                                                  |
| `docs/sdk-releases.md`         | every Katana release: date, the file names it circulates under (search terms), what it gave; prototypes and dev kit dumps as material                                                                                                                                                            |

### Tools for step 2: Signature-driven baseline

| script                               | what it does                                                                                                                                                                                                                                                                                     |
|--------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `scripts/tools/1-2-baseline/setup/ghidra/dghidra.sh`          | headless Ghidra in Docker (image from `scripts/tools/1-2-baseline/setup/ghidra/Dockerfile`, built on first use)                                                                                                                                                                                                           |
| `scripts/tools/1-2-baseline/setup/ghidra/*.java`              | seed + report (`DcPre`, `DcReport`), signatures (`ExportSigs`, `ApplySigs`), prototypes and structs from the SDK's headers (`ApplyHeaders`), queries (`Query`: decompiles with FPSCR's PR and SZ at 0 on entry, so float code reads as single precision instead of two branches per instruction) |
| `scripts/tools/1-2-baseline/setup/sdk_headers.py`             | an SDK's C headers copied in a form Ghidra's C parser reads (form feeds, Shift-JIS comments, `(Void)` parameter lists, empty attribute macros)                                                                                                                                                   |
| `scripts/tools/1-2-baseline/setup/sdk_sigs.sh`                | signature table for every exported function in an SDK's libraries                                                                                                                                                                                                                                |
| `scripts/tools/8-build/disc_patch.py`              | copy a GDI with files replaced in place, error correction recomputed                                                                                                                                                                                                                             |
| `scripts/tools/1-2-baseline/apply_bin.py`               | write a modified executable's changes into the repo's asm data words                                                                                                                                                                                                                             |
| `scripts/tools/1-2-baseline/split_asm.py`               | split an executable into per-function asmsh sources + link order                                                                                                                                                                                                                                 |
| `scripts/tools/1-2-baseline/units.py`                   | in the repo: the link order with C units in place of the asm files they replace                                                                                                                                                                                                                  |
| `scripts/tools/1-2-baseline/fill.py`                    | in the repo: lay a C unit out like the original (nop alignment, 0xEE fill, exact size; every other layout is an opt-in `+` option of the unit's header, `docs/matching-units.md`) |
| `scripts/tools/1-2-baseline/shc_flags.txt`              | in the repo: the `shc` flags of every C unit, read by `build.sh` and `fcmp.py` (a unit adds its own in its header; `+<x>flags` picks `shc_flags.<x>.txt`) |
| `scripts/tools/common/fcmp.py`, `scripts/tools/7-reduction/permute.py`     | in the repo: compare a C unit with the original function by function, instruction by instruction; try meaning-preserving rewrites of one function (matching) |
| `scripts/tools/overlay/`                                | in the repo: code overlays loaded from the disc (only a game with `overlays.tsv` uses them): survey, decompress and split, function lists, carry a unit to every copy, build and report (`docs/overlays.md`) |
| `scripts/tools/1-2-baseline/sdk_txt.py`                 | mark the SDK's code (boot block, library block, single matches) as `sdk.txt`                                                                                                                                                                                                                     |
| `scripts/tools/1-2-baseline/sdk_masked.py`              | after the tables: name more SDK functions by masked instructions, library layout and source listings (statics), link order as the check (stdlib)                                                                                                                                                 |
| `scripts/tools/1-2-baseline/missed_funcs.py`            | list code the analysis did not make into functions                                                                                                                                                                                                                                               |
| `scripts/tools/1-2-baseline/seed_funcs.py`              | function starts in stretches no function covers, seeds for `ghidra/SeedFuncs.java`                                                                                                                                                                                                               |
| `scripts/tools/1-2-baseline/setup/map_names.py`               | code symbols of a linked library's map, runtime routines included                                                                                                                                                                                                                                |
| `scripts/tools/4-boosts/elf_debug_names.py`         | function names and addresses from an SHC ELF's DWARF 1 debug section (prototype or dev kit ELFs)                                                                                                                                                                                                 |
| `template/disc.sh`                   | in the repo: build a playable disc image of the user's version                                                                                                                                                                                                                                   |
| `template/build.sh`                  | assemble, compile C units, link (`start P(<base>)`), `elf2bin`, compare with the original                                                                                                                                                                                                        |
| `docs/sdk-signatures.md`       | naming library code from the SDK's libraries                                                                                                                                                                                                                                                     |

### Tools for step 3: Asset mapping

| script                               | what it does                                                                                                                                                                                                                                                                                     |
|--------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `scripts/tools/3-assets/text_map.py`                | the executable's strings, text per disc file, the list of images                                                                                                                                                                                                                                 |
| `scripts/tools/3-assets/text_dump.py`               | copies the disc files `models.txt` lists as `text <path>` into `text-dump/`                                                                                                                                                                                                                      |
| `scripts/tools/3-assets/textures.py`                | every standard texture to PNG + a contact sheet (`index.html`)                                                                                                                                                                                                                                   |
| `scripts/tools/3-assets/find_extras.py`             | in the repo: the `extra` rules of a character draw function, found by running its branches per character (draws behind state the run cannot know are listed as gated, not as rules)                                                                                                              |
| `template/symbols.txt`               | in the repo: names the C uses that no file defines yet, empty but for the format line                                                                                                                                                                                                           |
| `template/textures.sh`               | in the repo: the texture contact sheet, as its own step                                                                                                                                                                                                                                          |

### Tools for step 4: Opportunity-driven optional boosts

| script                               | what it does                                                                                                                                                                                                                                                                                     |
|--------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `scripts/tools/4-boosts/sibling_names.py`           | names from a sibling decomp (same team, shared library): exact masked matches unique both ways, twins listed                                                                                                                                                                                     |
| `scripts/tools/4-boosts/cheat_leads.py`             | cheat codes (CodeBreaker/Xploder list) as named-variable leads                                                                                                                                                                                                                                   |
| `scripts/tools/1-2-baseline/setup/ghidra/ExportFeatures.java` | per-function strings, constants, calls and globals, for port matching                                                                                                                                                                                                                            |
| `scripts/tools/1-2-baseline/setup/port/*.py`                  | pair functions and globals with a port's symbols (`docs/port-symbols.md`)                                                                                                                                                                                                                  |
| `docs/port-symbols.md`         | naming from a later port that kept its symbols (Android, iOS, PC builds)                                                                                                                                                                                                                         |

### Tools for step 5: Incremental script-generated decomp

| script                               | what it does                                                                                                                                                                                                                                                                                     |
|--------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `scripts/tools/sim/sh4sim.py`                  | in the repo: an SH-4 interpreter (integer, single-precision FPU, delay slots) that runs one function from a case (registers, memory, a RAM dump, mocked call returns) and records its calls, writes and result (stdlib)                                                                          |
| `scripts/tools/sim/equiv.py`                   | in the repo: compiles a C file and checks each function against the original on its test cases (`tests/<file>/<function>.json`); the Equivalent tier, written to `tests/equivalent.txt`; each result also says how many of the original's instructions the cases ran (coverage)                  |
| `scripts/tools/5-generated/gen_equiv/`                 | in the repo as `tools/5-generated/gen_equiv`: writes Equivalent C for functions that need no thinking (script-generated: report it apart from hand C); `--regen <name> ...` writes generated functions again after a generator fix, keeping the old C unless the new is proven; `--retest` draws the cases again, guided by the original's instruction coverage, and lists functions whose C fails on them; `--draw src/<file>.c` draws coverage-guided cases for C you wrote by hand (arguments from the prototype, memory behind pointers, answers for calls) |
| `scripts/tools/5-generated/sdk_source.py`              | in the repo: compiles the library sources the user supplied with the SDK's shc; the functions whose bytes they reproduce go to `sdk-source/` (exact C, git-ignored) and `sdk-verified.txt` (names, counted by `progress.py`)                                                                     |
| `scripts/tools/5-generated/sdk_dups.py`                | in the repo: one C per function: lists the C in `src/` for functions the SDK's own source already reproduces; `--fix` removes the second C, its cases and its record                                                                                                                              |
| `scripts/tools/5-generated/sdk_place.py`               | in the repo: the SDK's C out of the game's `src/` into its library's folder, `sdk/<library>/`; prints the plan, `--fix` moves or splits the files, their cases following each function |
| `scripts/tools/5-generated/audit_equivalent.py`        | in the repo: every function in `tests/equivalent.txt` has C behind it (or is SDK-verified); `--fix` removes the rest (the pre-commit hook runs it)                                                                                                                                               |
| `scripts/tools/4-boosts/port_equiv.py`              | in the repo: carries Equivalent C for shared library code from a sibling decomp into this one (masked-code match, pool-word mapping, ported cases), every function re-checked by this repo's `equiv.py`                                                                                          |
| `scripts/tools/5-generated/remaining.py`               | in the repo: every function not done yet, by its current state and the cause it shares with others (`--table`) |
| `scripts/tools/5-generated/diverge.py`                 | in the repo: why one function's generated C differs from the original: the first mismatching call and where each argument came from |
| `scripts/tools/5-generated/overreads.py`               | in the repo: reruns the cases with junk in unused RAM, on the original and on the C, and lists the Equivalent C that reads memory the original does not (a report; it records nothing) |
| `scripts/tools/5-generated/rawcalls.py`               | in the repo: C that calls original code by a raw address no function in `functions.txt` starts at (`equiv.py` passes it, a build from C has nothing to call): a new one fails, `tests/rawcalls_allowed.txt` is a ratchet that only shrinks; `--update` drops the fixed, `--allow` rewrites the list, `--list` shows every one |
| `docs/matching-units.md`        | matching C units: the `@unit` header (`@data`, `@ddata`, `@bdata`, units in folders), the opt-in `+` options (`+pool32`, `+synth16`, `+<x>flags`, `+r04`, ...), `fcmp.py` and `permute.py`; what changes between the two modes |
| `docs/overlays.md`             | games with code overlays: `overlays.tsv`, `overlays/<name>/`, `build.sh --overlay`, `build_overlays.sh`, `in.sh`, carrying a unit to every copy |
| `docs/equivalent-pipeline.md`  | writing Equivalent C at scale: the three checks, what the check compares, the lock for parallel workers, the worker brief                                                                                                                                                                        |

### Tools for step 6: Experience-driven agentic decomp

| script                               | what it does                                                                                                                                                                                                                                                                                     |
|--------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `scripts/tools/1-2-baseline/checksizes.py`              | in the repo: functions whose size in `functions.txt` looks wrong (a literal pool mid-body ended the listing early), with the size that covers the code after it; `--hidden` finds the opposite, an entry listed longer than its code with another function inside it (counted proven, though nothing tests it) |
| `scripts/tools/5-generated/classify.py`                | in the repo: which functions can have C at all (FPU banks, `fsrra`, control registers other than SR: blocked)                                                                                                                                                                                    |
| `scripts/tools/6-agentic/poollist.py`                | in the repo: a function's literal pool as functions, RAM addresses (named, or MISSING) and numbers                                                                                                                                                                                               |
| `scripts/tools/sim/shdis.py`                   | in the repo: SH-4 disassembly with FPU, pool values and names (stdlib)                                                                                                                                                                                                                           |
| `scripts/tools/6-agentic/live.py`                    | in the repo, optional: read, watch and write the running game by address or name, screenshots, pad input (RetroArch + Flycast core over its network ports, stdlib)                                                                                                                               |
| `scripts/tools/6-agentic/gdbsnap.py` | in the repo, optional: RAM snapshots of the running game over Flycast's GDB server (a build with `ENABLE_GDB_SERVER`), timelines, and what changed between two snapshots with the nearest global names; live data in `docs/agentic-decomp.md` (stdlib)                                              |
| `scripts/tools/6-agentic/parts.py`                     | in the repo, step 6: an outlier function in parts: `map` cuts it along its dominator tree (`state/parts/<name>/parts.txt`), `read` has the generator read each part in a scratch copy (`<part>.c`, the material for the join by hand) |
| `scripts/tools/6-agentic/handcase.py`                  | in the repo: prove a function on cases written by hand, with the C the generator writes |
| `scripts/tools/6-agentic/PROMPT_prove.md`              | a prompt to hand an agent: prove one function, raising its coverage with the tools above |
| `scripts/tools/6-agentic/poolconst.py`                 | in the repo: the C's reads of the original's literal pools become constants (or the function's name) |
| `scripts/tools/6-agentic/codeaddr.py`                  | in the repo: a game function's address written as a number becomes its name; numbers inside a function are listed |
| `scripts/tools/6-agentic/unpoke_code.py`               | in the repo: takes the code out of what a test case may change (`layout.txt` `code`) |
| `docs/matching-c.md`           | getting a source file to match: units, flags, fill, idioms, compare loop                                                                                                                                                                                                                         |

### Tools for step 7: Code size reduction

| script                               | what it does |
|--------------------------------------|--------------|
| `scripts/tools/7-reduction/shrink.py`               | in the repo: regenerate functions and keep the new C when strictly smaller and still proven (`--regen`: any size; `--passes`: the rewrite strategies on the current C, per unit) |
| `scripts/tools/7-reduction/hoist.py`                | in the repo: hold a value the C recomputes at every use in a local, as the original held it in a register (`--loose`, `--apply`) |
| `scripts/tools/7-reduction/sizes.py`                   | in the repo: the compiled size of a function's C, literal pools and constants included |
| `scripts/tools/7-reduction/repeats.py`                | in the repo: the game functions whose original repeats one run of instructions many times (candidates for a loop written by hand) |
| `scripts/tools/7-reduction/PROMPT_handshrink.md`       | a prompt to hand an agent: a smaller C version of one function by hand, proven at the coverage bar |
| `scripts/tools/7-reduction/PROMPT_install.md`         | a prompt to hand an agent: a hand version checked again, its callers checked, put into the repo and proven there |
| `scripts/tools/7-reduction/PROMPT_pass.md`             | a prompt to hand an agent: a rewrite pass counted, tried in a scratch copy on the game's own code, then run |

### Tools for step 8: Build from C

| script                               | what it does |
|--------------------------------------|--------------|
| `scripts/tools/8-build/cbuild.py`                 | in the repo: the build from C, step by step (`make c` runs them in order) |
| `scripts/tools/8-build/fit.py`                    | in the repo: reads the linked map: every part inside its place, the room a part has by the optimizer's ratio |
| `scripts/tools/8-build/relocasm.py`               | in the repo: assembly pieces that can move (real instructions, labels, symbols) for functions with no C |
| `scripts/tools/8-build/relocptr.py`               | in the repo: pointer words to game functions, in what stays where it is, follow the functions |
| `scripts/tools/8-build/codeconsts.py`             | in the repo: C that reads a constant from the original's code by its address (a literal pool the build overwrites): lists them, `--write` puts the values in |
| `scripts/tools/8-build/retcheck.py`               | in the repo: each function's result register from the original's code before its `rts` against its C declaration; `make c` and the pre-commit hook run it, a mismatch refuses |
| `scripts/tools/8-build/protocheck.py`             | in the repo: calls that pass fewer stack words or argument registers than the callee takes; `--lost` keeps the ones where the original sets the register before the call, which `consistency.py` lists as `short call` and `--fix` hands back to the generator; a callee with no C in `src/` (library code kept as the original) is checked on the registers its original reads at its entry |
| `scripts/tools/8-build/disc.py`                   | in the repo: `make disc` runs it. Builds the way `status.txt`'s `MODE` says and writes the result into a copy of the disc: `equivalent` (or no MODE line) is `make c`; `matching` is `build.sh`, then `build_overlays.sh` when the repo has overlays, which must match |
| `scripts/tools/common/layout.py`                  | in the repo: reads `layout.txt` (the regions the build and the cases need) |
| `scripts/tools/8-build/PROMPT_triage.md`               | a prompt to hand an agent: a build from C that stopped, traced from its own message to the step that fixes it |
| `template/Makefile`                  | in the repo: `make` (the matching build), `make setup`, `make c` (`retcheck.py` first), `make disc`, `make progress` |

### Tools for all steps

| script                               | what it does                                                                                                                                                                                                                                                                                     |
|--------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `scripts/tools/progress.py`                | in the repo: done (equivalent C), matching C, named functions and globals, documented. "done: equivalent C" stays the first row of the first section: Pluto finds the main metric by that label                                                                                                  |
| `scripts/tools/toolpath.py`                | in the repo: every tools folder on the import path, so a tool imports another by name |
| `scripts/tools/common/boundaries.py`              | in the repo: function boundaries from reachability: which addresses are functions of their own (`--apply` writes `functions.txt`); `--discover [--values]` names the candidates (what listed code jumps or calls to; with `--values`, also the code addresses in pool words it loads and hands on); a `bra` or a conditional branch to another listed function is a tail jump, not more of the function |
| `scripts/tools/common/rename.py`                  | in the repo: rename functions and globals everywhere at once |
| `scripts/tools/common/consistency.py`, `ledger.py`, `status.py`, `watch.py` | in the repo: C and cases agree; nothing learnt about a function is lost; what is running; progress of a run |
| `template/setup.sh`                  | in the repo: extract + verify the user's executable, regenerate `asm/` and `text-map/`                                                                                                                                                                                                           |
| `template/README.md`                 | the repo's README, with `@PLACEHOLDERS@` to fill                                                                                                                                                                                                                                                 |
| `template/AGENTS.md`                 | the decompilation loop for whoever works in the repo                                                                                                                                                                                                                                             |
| `template/gitignore`                 | the repo's `.gitignore`: keeps game and SDK material out of git (asm, executable, disc, build, text map)                                                                                                                                                                                         |
| `docs/evidence.md`             | each game the skill was run on: numbers, what broke, what changed                                                                                                                                                                                                                                |
| `docs/memory-map.md`           | Dreamcast addresses worth labelling on sight                                                                                                                                                                                                                                                     |
| `docs/upgrade.md`              | bringing a repo this skill started to a newer skill version: versions, `KICKOFF`, the steps                                                                                                                                                                                                      |

