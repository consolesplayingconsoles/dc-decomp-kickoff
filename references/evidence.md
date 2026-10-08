# Evidence: games the skill has been run on

One entry per game. The rest of the skill states rules without naming games; what each game showed,
and what changed in the skill because of it, lives here. A lesson that comes back on several games
belongs in the rules; one that stays with a single game is that game's quirk.

The skill's last step prints a run in this format: paste it here (or send it to the skill's repo
as an issue) to add a game.

## Entry format

```
### <Title> (<region>), <product number> <version>
- run: <date>, skill <version or commit>, on <OS / cloud workspace>
- executable: <size> bytes, linked at <base>; SDK by banners: <release, n/m library builds>; SDKs used: <...>
- functions: <n>; named: <n> (<n> SDK signatures, <n> reference decomp); build: MATCH (also after setup.sh)
- text map: <strings, with pointers>; file tables: <files with a table in the executable>; textures: <n decoded>
- missed functions: <n candidates>
- C units: <matched units, functions>
- what broke or surprised -> what changed in the skill
```

### Crazy Taxi (Europe)
- run: 2026-10-05 (v0.4) and later sessions, on macOS (Docker)
- executable: linked at 0x0C010000 (most Katana games use 0x8C010000: imported at the wrong base,
  Ghidra found 1,113 functions instead of 2,389); SDK by banners: R9 closest (19 of 29 known
  modules, against 11 for R10.1); SDKs used: R10.1 (Kochise, and a second copy laid out like the
  reference decomp's: same results), later R9
- functions: 2,389; named: 429 at kick-off (385 SDK R10.1, 30 reference decomp, the rest
  wrappers); an R9 table named 112 more SDK functions (SDK coverage 42% to 53%); build: MATCH
- port: Crazy Taxi Classic 6.0 for Android (`libgl2jni.so`, arm64) kept its symbols: 310 functions
  and 29 globals paired, 257 new names (functions named 20% to 31%)
- text map: 2,513 strings, 1,144 with every pointer found; 16 image files flagged (5 languages);
  textures: 1 standard texture on the disc (the art is in the game's own formats)
- missed functions: 644 candidates, about half backed by a pointer
- C units: a Naomi-library file (3 functions) and the heap/event list (9 of 12) matching; SHC 5.1
  Release 04 (R1.42J), 08 (R9) and 11 (R10.1) compiled identically on everything compared
- what broke or surprised -> what changed:
  - wrong import base -> `linkbase.py`
  - a unit swallowed a 16-byte leaf the split did not have, build 16 bytes short -> `units.py`
    refuses units whose ends are not file boundaries; `missed_funcs.py`
  - library code (`nl*`) padded with nops to 16/32 bytes -> `-align16` in the unit header
  - register allocation decided by how C is written -> the idioms tables in `matching-c.md`
  - constant data had nowhere to go -> `@data` and `D` lines
  - functions reached only through a function-pointer table were merged into a neighbour ->
    `missed_funcs.py` flags pointers into a body
  - two signature names on game code were wrong (a state entry, an angle helper) and spread as
    port seeds -> `validate.py` lists short signature names with no family nearby
  - port work: PLT stubs hid callers (`Query.java callers`), relocations pair whole pointer tables,
    32-bit Dreamcast constants line up structs (+4 per widened pointer) -> `port-symbols.md`
  - SHC runtime routines (`__modls`, `__bfslu`, `__quick_*_mvn`) never named: typed as data in the
    library map -> `map_names.py`
  - code placed in the boot block's filler gave a black screen once gameplay started -> the
    "Changing the game" note in the template
  - 2026-10-08, the four early-SDK tables: +7 unique matches, 4 applied; 3 collided with
    confident names on tiny functions and were left out: `vmsio_init` on a 12-byte helicopter
    init, `nwSetWindowClip` on a 22-byte function the reference decomp names
    `nlObjPutUseViewMatrix`, `ADXERR_EntryErrFunc` on a 10-byte `njSetConstantAttr` -> the
    suspect-name rule in step 4 holds; cheat leads for the USA release carried to the Europe
    build by locating each variable in the code (two different shifts, two leads unconfirmed)
  - a menu handler reached only from a handler table started right after another function's
    mid-body literal pool, which neither rts nor padding seeding caught -> `seed_funcs.py`
    also seeds right after a pool (+47 candidates here, +71 on VF3)

### Boku Doraemon (Japan), T-41802M V1.003
- run: 2026-10-05 (v0.4) and 2026-10-06 (v0.5, on macOS and in a claude.ai cloud workspace: same
  names)
- executable: 978,148 bytes, linked at 0x8C010000; SDK by banners: no release has all 48 library
  builds (newest Shinobi 1.75, Oct 2000), closest R11b (26/48) then R10.1 (23/48); SDKs used:
  R10.1, R11b, 1.55J
- functions: 3,034; named: 1,164 on 2026-10-08 (1,091 from nine SDK tables merged, 18 from the
  complete Tokyo Bus Guide decomp, the rest wrappers; 1,060 the day before with three tables,
  975 at v0.4 with R10.1 and the 176-name reference); build: MATCH, also after setup.sh
- text map: 2,155 strings (80 Shift-JIS, 1,962 with pointers); file tables: STORY.PAC (76 scenes,
  sector and length at 0x8C04B704), KAOGRA.PAC, STORYGRA.PAC; textures: 887 decoded, 222 not
- missed functions: 860 candidates, plus 9 merged functions reached through tables
- C units: none yet
- proof beyond the build: rewriting STORY.PAC's table let the story script grow past its slot
  (moved into the filler track, 10 KB bigger, a scene at 1.7x its budget); played through in
  Flycast and on GDEMU. The game's Catalan translation went from about 40% to 99% this way.
- what broke or surprised -> what changed:
  - the scene table was found by `file_tables.py`; tested blind on 6 other games: no false hits
    and no hits, so a missing row proves nothing
  - per-release SDK tables named twin stubs (byte-identical code under unrelated names) by which
    release has which -> SDK tables are merged into one before applying
  - the cloud workspace dropped dotfiles and execute bits from the uploaded skill, and could not
    pull Docker images -> `template/gitignore` without the dot, `DC_LOCAL` for every script
  - 2026-10-08, four more SDK tables (R4, R1.42J samples, R1.42J, 2.00J): +122 SDK names on top
    of the 992 (measured in a scratch project): 86 from 2.00J (Sep 2000 libraries, the closest to
    this Oct 2000 game: Sofdec `MPS_`/`MPV_`, `mwRnv2`...) and 33 only from the R1.42J sample
    programs, whose Sofdec builds matched where no library did. Crazy Taxi: +7. More releases
    keep paying, each game by the one nearest its build date, and sample programs count

### Virtua Fighter 3tb (US), MK-51001 V1.002
- run: 2026-10-07, naming only (for another team's decomp; no repo kicked off), on macOS (Docker)
- executable: 1,179,648 bytes, linked at 0x0C010000 (16,517 pointers; 11 at 0x8C010000); SDK by
  banners: none of the game's 6 library builds (Jan 1999, GDFS 0.53 of Aug 1998) is in any
  preserved release: it sits between Katana 0.40 and 1.0B2; SDKs used: 0.40 Release.4, 1.55J, R9,
  R10.1, R11b
- functions: 1,906 at first (27% of the executable), 2,306 after seeding (32%); the other team's
  own baseline is 2,398 (37%): most of the executable is data
- named (after seeding): 126 (97 SDK, of which 0.40 added 44; 22 from the Crazy Taxi decomp's
  NAOMI library names; 3 from TBG; 4 wrappers); before seeding, 97 of 116 signature names did not
  appear anywhere in that team's repo
- what broke or surprised -> what changed:
  - 1998 libraries use another banner form -> `banners.py` / `sdk_scan.py` read both; 0.40 added
  - a sister decomp (same developer's library) named what no SDK could -> "From another decomp's
    names" in `sdk-signatures.md`
  - the other team's best SDK matches came from an SDK sample program's ELF of the exact library
    version -> "sample programs" note
  - analysis reached a quarter of the executable -> `seed_funcs.py` + `SeedFuncs.java`, coverage
    note in step 3
  - tiny collisions (a video-player function name in a fighting game) -> suspect-name note in step 4
  - PC (Sega ALLS, 2023) version: a modern host engine around the arcade original, no symbols
  - more 1998-1999 SDK tables tried after that (R4: 1,035 signatures; R1.42J's 13 prebuilt
    samples with their link maps: 2,141; R1.42J's own libraries, unpacked from its InstallShield 3
    installer with `is3_extract.py`: 2,943): +0, +0 and +1 names. The game's libraries are in no
    preserved release; the tables stay for the next early game
  - cheat codes (the Dreamcast-Talk CodeBreaker list, same release): 5 RAM variables named
    (both players' health, the round timer, the win counters), none of them in that team's repo
  - the 1998 Set 5.05 table from the Tower of Babel dev kit demo (below): +0, 1 ambiguous. VF3tb's
    Kamui is not Set 5's either

### Phantasy Star Online Ver. 2 (US), MK-51193 V1.004
- run: 2026-10-07, stopped at step 1
- the boot file (157 KB, Shinobi 1.757) has none of the game's text: a core that loads the game's
  code at runtime (the disc holds 129 `.BIN` and 516 `.REL` files); the big `2_DP.BIN` (2.8 MB,
  SDK R9 exact) is the bundled Dream Passport 2 browser, kicked off by mistake before checking its
  text (kept as its own local repo)
- ports checked for names: PC (no symbols, no `.pdb`), GameCube Episode I & II (no map; its extra
  `.dol`s are a web browser and its debug build), the GameCube decomp (9 game files, C++ classes
  whose names do not appear in the Dreamcast build): none carries names over automatically
- what changed: step 1 "check it is the game", runtime-loaded code named as a limit; "check for
  symbols first" in `port-symbols.md`

### Dev kit dumps (sega-dreamcast-info.com, 11 "Set 5" Katana kits on archive.org)
- run: 2026-10-08, three kits opened (Tower of Babel 70 MB, Rage Software 0.2 GB, Eurocom 1.4 GB)
- the disk images are the studios' project folders (NBA Hoopz, Hydro Thunder, UEFA Striker), no
  SDK install on any of them; the recovered-files archives hold the useful pieces. By design: the
  dev box's own disk holds GD-ROM emulation images (`.HCD`/`.VDS`), the SDK lives on the Windows
  host, so no dev box dump will ever carry an SDK release
- Tower of Babel: the demo's `1ST_READ` (Sep 1998) and its Hitachi link map, linked against
  `C:\KTN505` (Set 5.05, Aug 1998); the map matches the binary (the start-up stub's jump). 1,005
  code symbols -> `map_names.py` + `ExportSigs.java`: 690 signatures, the earliest table there is
  (`nw`, `kmi`/`km`, `gd`, `vms`, `mpd`, `sd`, `sy`, `kd`, `bu`). Set 5 era only: VF3tb +0
- Eurocom: `Hydro.elf` (Jul 1999, 26 MB) is the game's ELF with a 23 MB DWARF-1 `.debug` section
  and no symbol table; a 60-line DWARF-1 walk gives 2,753 named functions with addresses, all
  Eurocom's own code (the SDK libraries were linked without debug info), so it is a named
  reference for a Hydro Thunder decomp, not an SDK table. `kmtransform*.c` are VideoLogic's 1998
  KMTools sample sources
- Rage: UEFA Striker DC betas without maps, PSX source in a zip, nothing to take
- Hydro Thunder (Jul 28, 1999 prototype, Hidden Palace / archive.org, 258 MB): its `HYDRO.ELF` is
  the kit's, byte for byte, and `LOO3.R2` (a data pack) embeds the Hitachi link map of the Jul 16
  build: 3,027 code symbols, 1,032 of them library code. `sdk_scan.py` on the ELF: 18/18 library
  builds = Release 8 (Europe), and 964 of those 1,032 names are already in the R8E table; the 68
  left are Eurocom/Midway wrappers (`Bup*`, `dc*`, `SN_*`). Nothing new to hash, two things
  confirmed: `sdk_scan.py` works on an ELF, and a prototype's data files can carry the link map
- also pulled (`~/cpc/dreamcast/prototypes/`): Crazy Taxi Dec 3 / Dec 13 1999, Jan 14 2000 (the
  untitled "Dreamcast prototype" item is the same Jan 14 build) and VF3tb Jul 27 1999: only
  `1ST_READ.BIN` on each, no ELF or map; earlier revisions of the executable, nothing more
- what changed: dev kit dumps added as extra material (link maps, ELFs with debug info, source);
  a DWARF-1 reader is worth a script if a second ELF like this turns up

