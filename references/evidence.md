# Evidence: games the skill has been run on

One entry per game. The rest of the skill states rules without naming games; what each game showed,
and what changed in the skill because of it, lives here. A lesson that comes back on several games
belongs in the rules; one that stays with a single game is that game's quirk.

The skill's last step prints a run in this format: paste it here (or send it to the skill's repo
as an issue) to add a game.

## Entry format

```
### <Title> (<region>), <product number> <version>
- Run: <date>, skill <version or commit>, on <OS / cloud workspace>
- Executable: <size> bytes, linked at <base>; SDK by banners: <release, n/m library builds>; SDKs used: <...>
- Functions: <n>; named: <n> (<n> SDK signatures, <n> sibling decomp); build: MATCH (also after setup.sh)
- Text map: <strings, with pointers>; file tables: <files with a table in the executable>; textures: <n decoded>
- Missed functions: <n candidates>
- C units: <matched units, functions>
- What broke or surprised -> what changed in the skill
```

### Crazy Taxi (Europe)
- Run: 2026-10-05 (v0.4) and later sessions, on macOS (Docker)
- Executable: linked at 0x0C010000 (most Katana games use 0x8C010000: imported at the wrong base,
  Ghidra found 1,113 functions instead of 2,389); SDK by banners: R9 closest (19 of 29 known
  modules, against 11 for R10.1); SDKs used: R10.1 (Kochise, and a second copy in another layout:
  same results), later R9
- Functions: 2,389; named: 429 at kick-off (385 SDK R10.1, 30 from a names table since dropped, the
  rest wrappers); an R9 table named 112 more SDK functions (SDK coverage 42% to 53%); build: MATCH
- Port: Crazy Taxi Classic 6.0 for Android (`libgl2jni.so`, arm64) kept its symbols: 310 functions
  and 29 globals paired, 257 new names (functions named 20% to 31%)
- Text map: 2,513 strings, 1,144 with every pointer found; 16 image files flagged (5 languages);
  textures: 1 standard texture on the disc (the art is in the game's own formats)
- Missed functions: 644 candidates, about half backed by a pointer
- C units: a Naomi-library file (3 functions) and the heap/event list (9 of 12) matching; SHC 5.1
  Release 04 (R1.42J), 08 (R9) and 11 (R10.1) compiled identically on everything compared
- What broke or surprised -> what changed:
  - Wrong import base -> `linkbase.py`
  - A unit swallowed a 16-byte leaf the split did not have, build 16 bytes short -> `units.py`
    refuses units whose ends are not file boundaries; `missed_funcs.py`
  - Library code (`nl*`) padded with nops to 16/32 bytes -> `-align16` in the unit header
  - Register allocation decided by how C is written -> the idioms tables in `matching-c.md`
  - Constant data had nowhere to go -> `@data` and `D` lines
  - Functions reached only through a function-pointer table were merged into a neighbour ->
    `missed_funcs.py` flags pointers into a body
  - Two signature names on game code were wrong (a state entry, an angle helper) and spread as
    port seeds -> `validate.py` lists short signature names with no family nearby
  - Port work: PLT stubs hid callers (`Query.java callers`), relocations pair whole pointer tables,
    32-bit Dreamcast constants line up structs (+4 per widened pointer) -> `port-symbols.md`
  - SHC runtime routines (`__modls`, `__bfslu`, `__quick_*_mvn`) never named: typed as data in the
    library map -> `map_names.py`
  - Code placed in the boot block's filler gave a black screen once gameplay started -> the
    "Changing the game" note in the template
  - 2026-10-08, the four early-SDK tables: +7 unique matches, 4 applied; 3 collided with
    confident names on tiny functions and were left out: `vmsio_init` on a 12-byte helicopter
    init, `nwSetWindowClip` on a 22-byte function that is the NAOMI library's
    `nlObjPutUseViewMatrix`, `ADXERR_EntryErrFunc` on a 10-byte `njSetConstantAttr` -> the
    suspect-name rule in step 4 holds; cheat leads for the USA release carried to the Europe
    build by locating each variable in the code (two different shifts, two leads unconfirmed)
  - A menu handler reached only from a handler table started right after another function's
    mid-body literal pool, which neither rts nor padding seeding caught -> `seed_funcs.py`
    also seeds right after a pool (+47 candidates here, +71 on VF3)
  - 2026-10-08, a mode reading from the port's names was wrong (`MainMode` 1 taken for the arcade
    game; it is the normal one, the traffic centre 500 ahead of the car, not on it) and a mod bug
    (all traffic gone until retry) stayed unexplained by reading alone -> `live.py`: both settled
    in one session against the running game (RetroArch + Flycast), the bug as cars spawned and
    removed in the same frame

- SDK release (2026-10-08, `sdk_scan.py` against 16 tables): no full match and none possible. The
  libraries no release has carry a `zr` suffix (`Shinobi 1.62zr`, `bu 1.47zr`, `kd 1.48zr`,
  `pd 1.50zr`, `syHw 1.07zr`, `syInt 1.50rz`, Aug 17-30 1999) plus `KAMUI 1.11.0.1`, `mwRna 1.26`
  and the Oct 1999 `libintr`/`libspr`: Sega-internal library builds between R9 and R10, never in a
  shipped SDK. The rest is R9's (1999-04 to 1999-08), so R9's compiler (SHC 5.1 Release 08) is the
  matching-C toolchain to try before R10.1's Release 11
- SDK names past the tables (2026-10-12, `sdk_masked.py`): 52.1% to 82.1% of the library
  functions (534 to 1,061 of 1,293; the count grew by the starts it found), build MATCH. One run
  on the pre-pass repo, three rounds, about 15 minutes over 16 tables and the Shinobi listings
  (27 usable of 73). By pass: listings 228 (statics with their source names: `search_fat_dir`,
  `read_dir`, `DECtoBCD`), position 240, masked match 58, twins by link order 7. 271 starts the
  split had missed (stubs reached only through function tables, gaps after a pool). 14 wrong
  signature names on tiny thunks replaced (`vmsfs_ismount` -> `buIsReady`, `mwRnaSetSfreq` on
  an `ADXRNA_` stub)
- What broke or surprised -> what changed:
  - Equal spans between two anchors in R8E and 1.42J had every function inside shifted by 2
    bytes (another version of the module): position alone named the wrong offsets -> the
    stretch's masked code is scored (wrong layout 0.82, right one 0.998); a fixed cut lost good
    stretches (many score 0.84-0.97) -> proposals carry their score, disagreements go to the
    best by a 0.05 margin, a stretch under 0.6 proposes nothing
  - `thunk_FUN_` entries counted as names and blocked their neighbours -> treated as unnamed
  - Left: Kamui statics (its dump has no listings) and the libraries no release has
- NAOMI library (2026-10-12): the game's `nl*` layer (0x0C0739C0-0x0C089F26, 91 KB, between the
  game code and data) is the NAOMI SDK's library; Virtua Tennis carries the same block byte for
  byte (237 functions, 39 KB identical once masked) while the two games share no game code. The
  NAOMI SDK 001002's libraries named 87 more (block marked as a `range` in `sdk.txt`), its 21
  sample programs (`t.map` + `t.mot` S-records) 73 more: named functions 1,547 to 1,708 of
  2,779. Virtua Tennis: 1,159 to 1,375. Two of the libraries Crazy Taxi's banners listed as in no
  release (`libintr`, `libspr`) are NAOMI libraries
- What broke or surprised -> what changed:
  - Sample programs came as S-records, not ELF -> `sdk_masked.py` reads `<name>.mot` beside a map
- Virtua Tennis game naming (2026-10-12, its own repo): three things the run hit ->
  - Ghidra decompiled every float instruction as two branches on FPSCR's PR/SZ bits (unknown at
    entry) -> `Query.java` sets both to 0 at every function entry, in memory: float code reads as
    plain single precision. Set over every address instead, it broke functions that switch SZ with
    `fschg` mid-way: entries only
  - A 21 KB function (`playerControl`) no pass found: it sat in a 21 KB gap after its neighbour's
    analysed end, and `missed_funcs.py` skipped gaps over 2 KB as data -> big gaps now count a
    pointed-to address that looks like an entry (after an rts, or a prologue). Crazy Taxi: 437 to
    454 candidates, Virtua Tennis: 694 to 838
  - Library names the tables missed came from the sibling decomp by hand -> `sibling_names.py`;
    on Virtua Tennis's earlier list it proposes 4 names (`nlObjPutLoadTexture`, `nlSetIntrFunction`,
    `nlSetIntrPriority`, `nlSynchFunction`) and lists 10 twin groups (the second copies of the heap
    and event functions, ADX twins)
- Crazy Taxi live RAM capture (2026-10-12): RetroArch's Flycast core has no memory map
  (`READ_CORE_MEMORY` answers -1), and `READ_CORE_RAM` answers up to 3,000 bytes (a 3,500-byte
  reply never comes); writes went through a 1 s timeout each first -> `live.py` reads in 2 KB
  pieces, writes in 256-byte ones, and goes straight to the RAM view once the core has shown it
  has no map. A 16 MB dump takes about 90 s paused. `Query.java`: a Ghidra project can lack
  starts `functions.txt` has (2,389 vs 2,824 here): `dec` there now says to use `mkdec`, and a
  query that throws no longer loses the output of the ones before it

### Step 9 on Crazy Taxi: from a disc that fits to one that plays (2026-10-24)

- The fitting build froze before the SEGA logo, then at the memory card window, then twisted the cab driver's arms. Three causes,
  none a wrong C statement: each a belief of the pipeline that the hardware does not share, invisible to equiv.py by construction.
- Pool reads: generated C read float constants from the original's literal pools by address (`*(float *)0xC057A4C`, 500.0 in
  Init_SEGA_LOGO's pool); the build from C puts other code there. 399 reads in 162 files; `codeconsts.py --write` puts the values
  in. The checker runs the C against the original image, where the address does hold the constant. Also 5 function pointers and 101
  of those reads sat on lines starting with `*(`, which cbuild.py skipped as comment lines (tests/cbuild).
- Mid-function calls: Exec_LCD was cut at 210 bytes in functions.txt, over five functions and half of Exec_LCDLogoDemo, and its C
  called Exec_LCDLogoDemo+140; the build made a second copy of that function with an entry label there, where the original has
  r11-r14, PR and a stack argument pushed: six pops nobody pushed, a return into garbage, the freeze (the first frame with LCD
  access on). Three such cuts (Exec_LCD 32 bytes, Put_TotalDrum 166 with its pool mid-body, Put_Remain_Time_Gauge 170), four calls,
  one unlisted function (breathMove+232, a real entry). cbuild.py now refuses a call into a C function's middle (tests/cbuild).
- Result types: fcvHermiteAngle ends `ftrc fr1,fpul; sts fpul,r0` (an int angle in r0) and was declared float, returning the
  leftover fr0; its caller read r0: every curve-driven joint angle was garbage. CheckColliPoleEdge the same (0/1/2 in r0). The
  checker compares only the declared register. `retcheck.py` reads each function's ending and refuses a mismatch (tests/retcheck);
  on the repo it then found nlUnitNormalVectorCW/CCW (0/1 in r0, declared float, callers drop the value).
- Method, every time static: the frame it stops in (from what is on screen), its call graph from the original, the built image
  against the original (addresses inside the old code that no symbol owns; second copies; endings), then one function. About one
  session for the three. Flycast GDB breakpoints had never fired here (above), and no debugger was needed.
- State: BOOTS TO MENU and PLAYABLE ticked, STABLE `[?]` not tested yet; the operator plays on.

### Virtua Tennis (USA), MK-51054 V1.001
- Run: 2026-10-12 (v0.5) and later sessions, on macOS (Docker), started beside Crazy Taxi for a combined mod
- Executable: 2,084,052 bytes, linked at 0x8C010000; SDK by banners: R10.1 (25 of 30 library builds match R10.1/R11b;
  ADXT 5.66 is R9 only)
- Functions: 3,232 at kick-off; named: 1,250 at kick-off (SDK tables, the masked SDK pass with the Shinobi listings, the
  NAOMI library block, Crazy Taxi's shared names); the NAOMI sample programs named 126 more; build: MATCH
- Shared code: the NAOMI library and C runtime are byte for byte the same as in Crazy Taxi: 31 Equivalent functions
  carried over with `port_equiv.py`, each re-checked on this game's bytes
- SDK source (2026-10-14): 280 functions reproduced by the Shinobi and Kamui source dumps. Unlike Crazy Taxi, Kamui
  partly matches here (34 functions), so the two games were linked from different Kamui revisions
- Model map: 1,644 textures through the executable's lists; the HUMAN, SSELE and WTC_MAIN texture lists not found.
  Audio map: 1,546 sounds, about 83 minutes
- What broke or surprised -> what changed:
  - Two identical copies of the overlay lock functions; the signature name landed on the copy the overlay code does not
    call -> each copy gets its own name (`ovLockCs_8c200114`)
  - `gdFsCreateHnG` has its literal pool in the middle: `functions.txt` listed 92 of its 112 bytes in both games, and the
    port missed it (the pool and filler differ between the games) -> sizes corrected, ported by hand
  - `pdExecPeripheralServer` was listed with a data table after its 12 bytes of code, which `classify.py` read as
    control-register instructions -> size corrected, a `D` line for the table
  - The committed list counted 29 functions whose C an earlier port had overwritten -> ported again; `port_equiv.py`
    keeps what a port file already holds, and drops the C and cases of a function that does not pass
  - Three library functions are different builds in the two games: `nlCosf` and `nlCosh` (each constant one bit
    apart) and `nlRenderTextureInit` (this game also sets a ready flag) -> each game's own build in its own file
    (`vtsdk_g.c` here, `sdk_f.c` in Crazy Taxi), outside the port files
  - Callees the port cannot map (reached by a branch, not a pool word) -> named the same in both games
    (`nlFogTableSet`, `nlSpriteLoadTextureOnce_Sub`)

### Boku Doraemon (Japan), T-41802M V1.003
- Run: 2026-10-05 (v0.4) and 2026-10-06 (v0.5, on macOS and in Claude: same
  names)
- Executable: 978,148 bytes, linked at 0x8C010000; SDK by banners: no release has all 48 library
  builds (newest Shinobi 1.75, Oct 2000), closest R11b (26/48) then R10.1 (23/48); SDKs used:
  R10.1, R11b, 1.55J
- Functions: 3,034; named: 1,164 on 2026-10-08 (1,091 from nine SDK tables merged, 18 from a
  names table since dropped, the rest wrappers; 1,060 the day before with three tables,
  975 at v0.4 with R10.1 and that table); build: MATCH, also after setup.sh
- Text map: 2,155 strings (80 Shift-JIS, 1,962 with pointers); file tables: STORY.PAC (76 scenes,
  sector and length at 0x8C04B704), KAOGRA.PAC, STORYGRA.PAC; textures: 887 decoded, 222 not
- Missed functions: 860 candidates, plus 9 merged functions reached through tables
- C units: none yet
- Proof beyond the build: rewriting STORY.PAC's table let the story script grow past its slot
  (moved into the filler track, 10 KB bigger, a scene at 1.7x its budget); played through in
  Flycast and on GDEMU. The game's Catalan translation went from about 40% to 99% this way.
- What broke or surprised -> what changed:
  - The scene table was found by `file_tables.py`; tested blind on 6 other games: no false hits
    and no hits, so a missing row proves nothing
  - Per-release SDK tables named twin stubs (byte-identical code under unrelated names) by which
    release has which -> SDK tables are merged into one before applying
  - The cloud workspace dropped dotfiles and execute bits from the uploaded skill, and could not
    pull Docker images -> `template/gitignore` without the dot, `DC_LOCAL` for every script
  - 2026-10-08, four more SDK tables (R4, R1.42J samples, R1.42J, 2.00J): +122 SDK names on top
    of the 992 (measured in a scratch project): 86 from 2.00J (Sep 2000 libraries, the closest to
    this Oct 2000 game: Sofdec `MPS_`/`MPV_`, `mwRnv2`...) and 33 only from the R1.42J sample
    programs, whose Sofdec builds matched where no library did. Crazy Taxi: +7. More releases
    keep paying, each game by the one nearest its build date, and sample programs count

### Virtua Fighter 3tb (US), MK-51001 V1.002
- Run: 2026-10-07, naming only (for another team's decomp; no repo kicked off), on macOS (Docker)
- Executable: 1,179,648 bytes, linked at 0x0C010000 (16,517 pointers; 11 at 0x8C010000); SDK by
  banners: none of the game's 6 library builds (Jan 1999, GDFS 0.53 of Aug 1998) is in any
  preserved release: it sits between Katana 0.40 and 1.0B2; SDKs used: 0.40 Release.4, 1.55J, R9,
  R10.1, R11b
- Functions: 1,906 at first (27% of the executable), 2,306 after seeding (32%); the other team's
  own baseline is 2,398 (37%): most of the executable is data
- Named (after seeding): 126 (97 SDK, of which 0.40 added 44; 22 from the Crazy Taxi decomp's
  NAOMI library names; 3 from a names table since dropped; 4 wrappers); before seeding, 97 of 116 signature names did not
  appear anywhere in that team's repo
- What broke or surprised -> what changed:
  - 1998 libraries use another banner form -> `banners.py` / `sdk_scan.py` read both; 0.40 added
  - A sister decomp (same developer's library) named what no SDK could -> "From another decomp's
    names" in `sdk-signatures.md`
  - The other team's best SDK matches came from an SDK sample program's ELF of the exact library
    version -> "sample programs" note
  - Analysis reached a quarter of the executable -> `seed_funcs.py` + `SeedFuncs.java`, coverage
    note in step 3
  - Tiny collisions (a video-player function name in a fighting game) -> suspect-name note in step 4
  - PC (Sega ALLS, 2023) version: a modern host engine around the arcade original, no symbols
  - More 1998-1999 SDK tables tried after that (R4: 1,035 signatures; R1.42J's 13 prebuilt
    samples with their link maps: 2,141; R1.42J's own libraries, unpacked from its InstallShield 3
    installer with `is3_extract.py`: 2,943): +0, +0 and +1 names. The game's libraries are in no
    preserved release; the tables stay for the next early game
  - Cheat codes (the Dreamcast-Talk CodeBreaker list, same release): 5 RAM variables named
    (both players' health, the round timer, the win counters), none of them in that team's repo
  - The 1998 Set 5.05 table from the Tower of Babel dev kit demo (below): +0, 1 ambiguous. VF3tb's
    Kamui is not Set 5's either

### Phantasy Star Online Ver. 2 (US), MK-51193 V1.004
- Run: 2026-10-07, stopped at step 1
- The boot file (157 KB, Shinobi 1.757) has none of the game's text: a core that loads the game's
  code at runtime (the disc holds 129 `.BIN` and 516 `.REL` files); the big `2_DP.BIN` (2.8 MB,
  SDK R9 exact) is the bundled Dream Passport 2 browser, kicked off by mistake before checking its
  text (kept as its own local repo)
- Ports checked for names: PC (no symbols, no `.pdb`), GameCube Episode I & II (no map; its extra
  `.dol`s are a web browser and its debug build), the GameCube decomp (9 game files, C++ classes
  whose names do not appear in the Dreamcast build): none carries names over automatically
- What changed: step 1 "check it is the game", runtime-loaded code named as a limit; "check for
  symbols first" in `port-symbols.md`
- What it would need: a second phase. The skill expects the whole game in one executable at a fixed
  address; PSO loads its game code into RAM at runtime from other files on the disc. Asked on the
  Dreamcast-Talk thread how PSO DC loads its code; nothing from the PC or GameCube builds carried over

### Illbleed (Japan, Crazy Games), T45601M V1.003
- Run: 2026-10-13, on request from a Dreamcast-Talk member as a Spanish translation target; the
  Japanese release, as they suggested
- Executable: 1,391,108 bytes, linked at 0x8C010000; SDK by banners: libraries dated 1999 to Nov
  2000, no preserved release contains them all; SDK era: KAMUI 1.11, Shinobi 1.76, Ninja
  01100114, ADX 5.93
- Functions: 4,245; named: about 2,000, mostly Sega library code; build: rebuilds the executable
  byte for byte
- Text map: the executable has almost no text of its own (developer error messages). The game keeps
  its text in separate message files on the disc, one set per language (found from the file
  names), so nothing has to be decompiled to reach it; textures: 17,269 dumped to one page for a
  person to look through
- The disc also carries the Dreamarena online browser, a separate program: left out of the analysis
- What it showed: a translation here is doable, with four jobs the skill does not do for you:
  the message files are not plain text (their format has to be worked out); the font needs room
  for Spanish characters (ñ á é í ó ú ¿ ¡); Spanish runs longer than English and the game may have
  fixed buffers (a long-text test, as on Boku Doraemon, shows it); text drawn into images has to be
  found by eye on the texture page. The same four were solved on Boku Doraemon
- What changed in the skill: the text map lists every image (`images.tsv`) instead of guessing
  which ones have text

### Dev kit dumps (sega-dreamcast-info.com, 11 "Set 5" Katana kits on archive.org)
- Run: 2026-10-08, three kits opened (Tower of Babel 70 MB, Rage Software 0.2 GB, Eurocom 1.4 GB)
- The disk images are the studios' project folders (NBA Hoopz, Hydro Thunder, UEFA Striker), no
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
- Also pulled (`~/cpc/dreamcast/prototypes/`): Crazy Taxi Dec 3 / Dec 13 1999, Jan 14 2000 (the
  untitled "Dreamcast prototype" item is the same Jan 14 build) and VF3tb Jul 27 1999: only
  `1ST_READ.BIN` on each, no ELF or map; earlier revisions of the executable. A strings diff
  against the release still paid: Dec 3 keeps a debug readout ("Beta Version DEBUG ASCII") whose
  printf labels name the cab driver's struct fields (`ManType`, `Act`, `Mode`, `ParamA`, `ParamB`,
  `Addr`, `Frm`, `isIp`), and pairing functions build to build (pools, pool addresses and `bsr`
  offsets allowed to move) shows what changed late: Jan 14 differs from the release in 58 functions
- What changed: dev kit dumps added as extra material (link maps, ELFs with debug info, source);
  a DWARF-1 reader is worth a script if a second ELF like this turns up

### SDK headers as types (R10.1 headers on the Boku and Crazy Taxi projects)
- Run: 2026-10-08. 174 headers; what Ghidra's C parser tripped on, all handled by `sdk_headers.py`:
  form feeds between declarations (every Kamui API header), `(Void)` / `(VOID)` / `(KMVOID)` as an
  empty parameter list (a typedef of void is "not permitted" as a parameter), Shift-JIS comment
  bytes, `KMAPI` / `IN` / `OUT` / `CRIAPI` attribute macros, a missing `machine.h`, and headers
  that use a type a later header defines (second parse pass). One header still fails and should:
  `sg_sm.h` declares `smVcntInitG(OvLib ovl)` with a type no R10.1 header defines (`OVLIB` exists,
  `OvLib` does not), a bug in the SDK itself
- Parsed: 2,372 function prototypes, 423 structs. Applied: Boku 216 of 1,157 named functions,
  Crazy Taxi 143 of 546; the rest are library internals (`mw*`, `kmi*`, `vmsfs_*`, `mpdrv_*`,
  `sd*` internals) that no public header declares. Pool words pointing at prototyped functions
  typed (Boku 795), every pool word pointing at a function marked constant (7,303)
- Effect: `pPVar2 = (*PTR_pdGetPeripheral)(0x12)` now carries `PDS_PERIPHERAL *`; the decompiler
  does not fold the constant pool pointer into a direct call, so the call keeps its pointer name


### Equivalent tier (2026-10-12, Crazy Taxi's `src/extrand.c`)
- The bar for game code changed from byte-matching to behaviour: `scripts/tools/sh4sim.py` (an SH-4
  interpreter, stdlib) runs a function from a case, `scripts/tools/equiv.py` compiles a C file and
  runs each function twice per case (original bytes, compiled C), comparing calls out (target,
  r4-r7, fr4-fr11), memory writes and the return register taken from the C prototype
- First run: `extRand` (no byte match: its mask lands in r2, the original's in r3, after 22
  wordings) is Equivalent on 6 seeds; `extRandomSeed` and `extRandom` too. Two planted bugs (the
  seed's 0x3039 as 0x3038, the scale 1/32768 as 1/32767) were caught as a different write and a
  different return value
- What broke -> what changed: the C's call to its own `extRand` went to the C copy's address, and
  `extRandom` left a pointer in r0 -> calls and writes into the file's own names are mapped back
  to the game's addresses; only the prototype's return register is compared. Docker cannot mount
  macOS's /private/tmp: run the check inside the repo (its `build/equiv/`)

### Equivalent C past 40%: where the cheap gains end (Crazy Taxi, Virtua Tennis; 2026-10-17)
- Run: CT 33.6% -> 40.7% and VT 12.7% -> 26.7% in one day, from four sources in order of yield:
  hand-written SDK C (CT, ~500 functions), `gen_equiv` on straight-line code (CT ~500, VT 367 in
  one run), `port_equiv.py` CT -> VT (+87 functions, 65 renames), then the dry tail below
- The dead zone: once the straight-line functions are generated and the shared SDK is ported, what
  is left is not small. CT after the last run: 81 candidates the generator cannot read; VT: 215.
  Skip reasons, VT / CT: backward branch (loops) 207 / 81, unconditional forward `bra` 129 / 90,
  address-of-local 168 / 76, stack-argument push 81 / 47, dirty register 53 / 43, indirect call
  35 / 33, `stc` 28 / 21. The generator's extra support for `mul.l`/`muls.w`/`mulu.w` bought 1 CT
  function and 6 VT ones: those instructions sit behind loops and jumps, not on their own
- Dead ends, so other games skip them:
  - Porting the other way (VT -> CT) after CT -> VT: 17 matches, 2 renames that broke callers, 1
    DIFFERS; net negative, reverted. Once the shared library is ported one way there is nothing left
  - `_divls`/`_modls`/`_divlu`/`_modlu` as C `/` and `%`: the helpers take operands in r0/r1 and the
    build's `-division=cpu` turns a constant divide into shifts, so the C does not make the call
    `equiv.py` compares; not Equivalent (see `src/sound.c` in CT)
  - Float early returns (`nlCot`, `nlSec`): the generator's void variant drops the returned value
  - `sdk-doc` (Katana SDK Sources/Documentation/KATANAStudy samples): PC-side window/animation
    helpers and ELFs of the Apr-May 1998 release (GDC 0.51, GDFS 0.49); no overlap with 1999-2000
    games, stripped, MSVC maps. Nothing to hash
- Next levers, not built: loops (emit loop-carried variables for do-while/counted loops), forward
  `bra` over else-blocks, name resolution of "N identical candidates" by callers and callees, the
  exact SHC flags for a byte-matching library build
- What changed: the skill's `gen_equiv` is the tool for the straight-line tail; expect a quarter to a
  third of a game's functions from it and `port_equiv.py`, then hand work or loop support

### gen_equiv reads branches and loops (Crazy Taxi, 2026-10-18)
- Run: `python3 tools/5-generated/gen_equiv 200` on a copy of the CT repo (working tree with the corrected function sizes), functions of up to
  200 bytes not yet covered. Before: the generator wrote C for 2 of them (the straight-line leftovers). After: **113 functions
  Equivalent** on `equiv.py` (44 with loops, 55 with `if`/`else`/early returns, 14 straight-line that earlier skips had hidden);
  38 of the 113 are 129-200 bytes (`classify.py` without names stops at 128, so the old run never looked at them)
- Why they were blocked: the generator ran the code top to bottom, so a forward `bra` that was not the else-jump of an `if`
  ("bra inner", 44 of the skips), any backward branch ("backward" 27, "bra back" 8) and a `return` inside a block ("rts in
  block" 12) stopped it, and a literal pool in the middle of a function was read as code. It now follows execution through a
  control-flow graph (`gen_cfg.py`): each branch becomes an `if`/`else` up to its nearest common successor, a loop becomes
  `while` / `do-while` / `for (;;)` with the registers that carry a value from pass to pass as C variables (found by a trial
  pass with a marker on each candidate: only the ones the next pass reads need a variable)
- What the tests needed: a loop runs as often as its bound says, so the cases for a loop function use small values, and
  every case is first run on the original: a case where it does not finish, or reads an unaligned pointer, is dropped (at
  least 12 must stay). Memory behind a pointer argument is filled, since the addresses a loop or a loaded pointer reaches
  cannot be worked out from the arguments
- Known-equivalent check (`gen_equiv --known`, 128 bytes or less): C is written again for functions already proven by hand
  or by an earlier run, and tested. Old generator 539 of 631 candidates, new one 758 of 844 (+225, no change in the straight-line
  output). Six the old one passed were first missing in the new run: `kmiWriteRegister` (a bug of this change, a large
  constant printed as a subtraction: fixed) and `FUN_0c02f14c` (passes on its own; dropped with a neighbour's compile error);
  `nlLog`, `FUN_0c07e880` and `nlsndCheckPackFreeError` (the size in functions.txt cuts the function off; the old reader
  stopped at the first `rts` and ignored the rest: the new one says "runs off the code"); `syCfgGetLanguage` (the old C
  stopped after an early return in a block and still passed 22 cases, which never took the other path: luck; the new reader
  refuses it, address of a local). So the old "Equivalent" of those four is not worth much: rerun `equiv.py` on them once the
  sizes are corrected
- Still skipped (CT, 200 bytes): address-of-local, indirect call (56), jump table, stack arguments, calls to the compiler's
  `_divls`/`_modls`/`_quick_odd_mvn` helpers (49: the generator cannot say what they take), a loop that changes a stack local,
  an address that the argument values alone do not give (array index with `<<`/casts)

### From 50% to 62% on Crazy Taxi, and Virtua Tennis 29% to 48% (2026-10-19)

What moved the numbers, in order of size:

- **Callee argument counts (gen_equiv).** The generator took a call's arguments from the registers set at the call, so two calls to
  one function often disagreed (leftover registers) and the function was skipped ("proto conflict"). It now reads the callee's own
  code for the argument registers it uses before writing them (`callee_arity`). Crazy Taxi: 50 more functions; Virtua Tennis: 546.
- **Library source with a missing header.** The Shinobi backup library source needs a private header (`sg_bup2.h`) that no SDK
  folder holds. Seven names were missing; a reconstruction in the repo's `sdk-headers/` (the file handle's layout read from the
  game's own `vmsfs_fopen`) made the library compile, and the byte comparison keeps only what matches. `tools/5-generated/sdk_source.py` also
  stubs any other missing header, and `sdk-patches.txt` (file, old text, new text) edits the staged source: the game was built with
  the library's `USE_STATIC` off, which took 366 verified functions to 396. About 40 functions of that file differ in code, not in
  values: probably another version of the library.
- **Many hand-checked functions are already counted.** SDK-source verification overlaps hand-written C: 104 newly verified
  functions moved the Crazy Taxi count by 27.
- **Wrong sizes in functions.txt**: `checksizes.py` fixed 410 (the code after a literal pool); a second heuristic flagged
  functions the simulator handles fine and was dropped (26 of its candidates were already proven).

Mistakes worth not repeating:

- In a test case, a float register (`"fr4"`) and a mocked float result (`"fr0"`) are the bit pattern as hex in reading order
  (`40A00000` is 5.0). Memory pokes are bytes (`0000A040`). Writing the register value as the memory bytes gives a denormal, and the
  case still passes, only weakly.
- `equiv.py` records every function it passes in `tests/equivalent.txt`, also for a scratch file. A generator run that is killed
  leaves names with no C behind them, and the count inflates (Virtua Tennis showed 44.5% instead of 29.2%). `gen_equiv` now puts
  the evidence files back after each round; `tools/5-generated/audit_equivalent.py` finds (and `--fix` removes) such entries, and the pre-commit hook runs it.
- Two `gen_equiv` runs on Virtua Tennis stalled in a later round and a third did not; the cause was never found. An alarm-signal
  time limit (`READ_LIMIT`, `BUILD_LIMIT`) cannot interrupt a hang in compiled code, so it may not catch such a stall. `GEN_TRACE=1`
  prints the function being processed, which names the culprit if it happens again.

### How good "Equivalent" is: instruction coverage (Crazy Taxi, 2026-10-19)

- **Measured.** `equiv.py` now reports, per function, how many of the original's instructions the cases ran (the listed bytes without literal
  pools and without the padding after the last return). Over the whole of Crazy Taxi: hand-written C 98.1% (949 of 998 functions
  completely covered, 20 under 80%); generated C 68.9% (346 of 599 completely covered, 182 under 80%).
- **Why generated C was low.** Random inputs cannot get through a chain of guards (a flag that must be 1, then the next flag, then the
  next): the first cases stopped at the first guard. `FUN_0c05a5e0`, nine such guards in a row, ran 27 of 151 instructions.
- **What fixed the cases.** `gen_equiv` now draws many candidate cases, runs the original in the simulator on each, and grows the set:
  it takes a case that reaches a lot of code, sets one of the memory words the original read last (or a register, or a call result) to a
  value the code compares against, and keeps the new case if it runs an instruction no case has run. `FUN_0c05a5e0` went from 27 to 124
  of 151 instructions with the same C. `gen_equiv --retest` does this for functions already generated.
- **What it found.** The new cases showed generated C that was wrong on a branch the old cases never reached: `FUN_0c02f02a`,
  `setObjGroupExec`, `FUN_0c15c8dc`, `FUN_0c0217b4`, `Drv_Execute` and `ADXT_DiscardSmpl` (the run was interrupted, so the list is
  partial). Those functions keep their old cases until the C is fixed.
- **Not finished.** The re-draw over all generated batches never completed (it was interrupted twice and has no way to skip batches already
  done), so the totals above are the pre-re-draw ones.
- **What changed in the skill.** The run is organised as six steps (setup, baseline, asset mapping, optional boosts, script-generated decomp,
  agentic decomp) with the same titles in the README, `SKILL.md` and the repo's `AGENTS.md`; generated C is the lower tier and reported
  apart; sibling decomps and ports are an offer the user names, never a search; `roadmap.md` was retired into
  `references/agentic-decomp.md`.
- **Retry rounds barely pay; untried functions do.** `gen_equiv` used to run five rounds (the first, then retries of the failures
  with other code shapes). Over two Crazy Taxi runs the first round passed 98 of 131 candidates and the retry rounds 4 more, at as
  much time again. The generator now runs the first round only. A function it fails is left alone until something changes around
  it: a proven neighbour in the address space fixes its start and end (the sizes tools `checksizes.py` check), and a proven caller
  shows its argument types, return use and what it expects the function to do. Work the functions that have no attempt yet first.

### From proven C to a build from C (Crazy Taxi, 2026-10-22 to 2026-10-23)
- Start: all 3,321 functions that can be C proven Equivalent. Room for the game block: the old game code (342,336 bytes) and the
  fill in the file before it (58,328): 400,664. The libraries, data and SDK stay where they are; 181 pointer words follow the code.
- Measuring: a function's size as the distance to the next symbol left out its literal pool (the compiler puts a file's pool after
  its last function), so the first fit estimate ("fits with 8.5 KB spare") was 27 KB optimistic. The real number came from linking:
  421,966 bytes of code and 24,884 of constants. Only a link measures a build.
- What closed the gap, largest first: frame arrays without a zero initialiser (the copy from a zero constant cost 24.9 KB of data and
  5.5 KB of code over 268 functions); one literal pool per unit of merged generated files and short calls inside a unit (1.6 KB);
  the byte mover `_slow_mvn` as a struct copy instead of a load and a store per byte (864 bytes in one function); a value the
  original loaded once held in a local instead of reloaded at each of 57 uses (764 bytes in one function); the 8 functions that do
  need a zeroed frame zeroed by a loop (1,680 bytes of constants); 45 small functions shrunk with the pool counted (332 bytes).
  Result: fits with 16 bytes spare; the image has the original size; outside the game code only the pointer words differ.
- Dead ends (so the next game skips them): trying every generator switch on the biggest functions (no gain on any); holding
  repeated values where stores may change them (3 of 4 not equivalent); bigger units (worse: callers and callees end up far apart);
  the order of declarations (no effect on the frame); leaving out code a static scan calls unreferenced (it cannot show a function
  is never reached: the build has to stay the whole game). Shrinking the biggest functions again after earlier passes found nothing:
  the gains came from small functions and from patterns.
- What the build exposed: merging files under one old-style declaration changed call arguments in 19 functions (units now merge only
  files whose declarations agree). Calls that drop arguments the callee reads: the generator counted arguments from a scan that stops
  at the first return and does not see a register passed on to a call through a pointer; 460 game functions call with fewer
  arguments than the callee takes, and the check compared only the arguments the C declares, so they proved. Two of them crashed the
  boot (an interrupt registered without its callback; the VMU file system's callbacks registered without theirs).
- Debugging on the running game: Flycast's GDB server ignores breakpoints in this build (with and without the dynarec). Sampling the
  program counter, and comparing memory with the original disc at the same moment, found both crashes.

### Step 8 after the argument fix: what regenerating cost (Crazy Taxi, 2026-10-23)
- The regeneration: once the generator counted pass-through arguments, 453 functions were regenerated with `shrink.py --regen`, which
  keeps the new C at any size. The earlier shrinking of those functions was discarded and nothing in the log said so. Of the 370 with a
  known earlier size, 346 came out bigger, +49,640 bytes in all (PutCourse 5,000 -> 24,908). The build went from fitting with
  16 bytes spare (and a boot crash) to 36,900 over. Re-shrinking brought PutCourse back to 5,044. Regenerate only what is wrong, or keep
  the old C where the new is not smaller, and write the size cost in the log when the pass is run.
- What the log says is not what the build says: two builds measured 10,248 and then 7,204 bytes over, a real gain of 3,044, while the
  shrink log summed to 22,460 over the same functions (14%); the earlier build had 68%. Only a link measures; a sum of per-function
  sizes does not (pools and merged units change the total).
- The shrink list held 853 of its 1,439 remaining functions outside the game range (library, SDK, runtime), which the build keeps from
  the original. Filter a list to the range the build replaces before a run.
- A current C that cannot be measured is not "not smaller": the size check put it under the prototypes of the new generation, where
  a callee declared float and tested with `!` does not compile ("Scalar required for !"). Measured under its unit's own
  declarations it compiles. The log now says "not measurable", and the recheck's failing case (kept in state/results.jsonl all along)
  goes into the log with the new C in build/shrink-failed/.
- The proof cache key hashes the source of equiv.py and sh4sim.py, so any edit to the checker voids every pass. A saved copy of the
  old checker (state/proof-key-equiv.py) keeps the keys of functions the change cannot affect.
- Open generator limits (tests in tests/gen_equiv fail by design, OPEN): words pushed for a call whose cleanup is merged with the
  frame teardown in one `add` before the epilogue are read as spills and dropped (replayChangeControl, adxt_stat_decinfo,
  mwSbOpenPort; the generator writes `printfn()` with no arguments); phantom parameters on regenerated functions with no known cause
  (Drv_StartGetOn, kmiInitPAL, ShallWeHaveSomeRelaxation); compiler helpers with their own convention are refused (_fmtout).
- One function sat at 98% CPU in the generator with no limit (probably SetTotalRecords): the shrink has no time limit per function.
- Dead ends added: shrinking library functions to fit the game block (no effect on it); estimating the fit from the log (wrong twice,
  by 12,000 bytes once).
- What the original compiler did that the build does not (Crazy Taxi, 2026-10-23): calls between functions of the same source file are
  `bsr` (2 bytes, no pool word). Of the original's 734 `bsr` calls between game functions, 674 have caller and callee in different
  units of the build from C (units are made from the generator's batch files, not from the original source files), so they are
  `mov.l` + `jsr` + a pool word, about 6 bytes more each: roughly 4 KB of the 7,204 bytes over. 22 are in the same unit and still
  long; 36 are still short. The lever is the unit step (group by the original files), not the shrink, which measures each function
  alone where every call is long. Read from the build's units.json and the original's reachable code; not tried.
- Dead end (Crazy Taxi, 2026-10-23): a mnemonic histogram of the original against the build over the game range showed 36% more `mul.l`
  (3,967 against 2,913), but most of it was data words that decode as instructions (the original has 37,000 data words in that range,
  the build 9,800). Counted per function over the code only: 210 against 258 `mul.l` in the 97 functions that differ, concentrated
  in two (gdc_CourseObjGroupSet 7 -> 31, gdc_CourseAdvLoadReq 33 -> 47), at most about 300 bytes. Count per function, not over a range.
- From a matching decomp (Tokyo Bus Guide, `docs/lessons_learned.md`), C shapes that change SHC's output: a nested `if (a) { if (b) break; }
  else if (c) break;` leaves the first `break`'s jump as dead bytes; two independent `if`s with `continue` after the first, or the two
  conditions joined with `&&`, remove them. A pointer-walk loop with a separate trailing counter is SHC's strength reduction of one
  indexed loop, and the plain indexed loop compiles differently. `T buf[N] = {0}` puts N bytes of zeros in the constant section. Not
  tried on Crazy Taxi: the generated loops are `for (;;)` with `break`, so they are candidates for extra forms in the shrink.
- Hitachi's inter-module optimizer (`OPTLNKSH.EXE`, Ver. 1.1 Release05, in SDK r10.1 beside `lnk.exe`; Sega's note in the r1.55j
  SDK, `dc_sdk/optlnksh.txt`), measured on Crazy Taxi's game block (2026-10-23): compile the C with `-goptimize` (the code does not
  change; it writes one `.iop` per source under `shciop/`), link with `optlnksh -optimize=<items>` instead of `lnk`. One link of the
  same 414 objects at one address: plain 404,888 bytes; `branch` 403,540 (-1,348); `same_code` -20; `branch,same_code` -1,368;
  `branch,same_code,register,string_unify` 397,148 (-7,740); `safe` -7,716. The default (`-optimize`) also deletes symbols and does
  not link this build. Running it under wibo: `optlnksh` starts `OPTSH.EXE` and `lnk.exe` itself and only finds them in its own
  folder (a Unix or Windows PATH does not help), and the SHC driver rejects a path with a `-` in it. Messages: the same as the plain
  link (no new kinds). Not yet in the build: the layout is decided from module sizes before the link; the optimized bytes are not
  the bytes the checker proved (calls between C modules may skip register saves); asm objects are not optimized.
- With the optimizer in the build (Crazy Taxi, 2026-10-23, `cbuild.py fit`): fits. Part 1 (fill block) 58,256 of 58,328 bytes,
  part 2 (old game code) 340,860 of 342,336, nothing in the overflow, the image the original size; outside the game code 524 bytes
  differ (the pointer words). It took filling each part by its own measured ratio (part 1 shrinks 1.3%, part 2 1.5%: one ratio for
  both overfilled part 1 by 236 bytes). The optimizer prints ** 1170 ADDRESS SPACE DUPLICATE from its first, unoptimized pass,
  where parts filled for the optimized sizes overlap; the result is judged from the final map and the ELF segments. Once the
  optimizer crashed (PROGRAM ERROR(1704)) and wrote an empty map. Boot not tested yet.
- Boot test of the fitting optimized build (Crazy Taxi, 2026-10-23): the loading message, then black. Found with Flycast's GDB server
  (`cpc/scripts/flycast_gdb.py`: PC samples and memory reads): the CPU loops in the build's table pieces at 0C013A44-0C013E0C with
  interrupts masked; the SDK's `vmsfs_c_progress` had jumped to the game's VMU callback `BupProgressCallback`, placed at 0C013150, and
  that memory is zero at run time. The game clears 0C010100-0C014000 (the boot block, copied to 0C004000 and run there; docs/engine.md
  says so), and the layout's fill block started at 0C011C28, inside it: everything placed in 0C011C28-0C014000 is wiped. The usable
  fill is 0C014000-0C020000 (49,152 bytes, not 58,328). Not the optimizer: the callback's code is the same in the plain and the
  optimized links.
- Release flags (Katana SDK r9, `shinobi/sample/dc.inc`, the sample makefile games started from): debugging on `-size -debug`,
  debugging off `-speed -nodebug`; the SDK's own libraries are built `-optimize=1 ... -size` (which is why they reproduce byte
  for byte with the build's flags). A release game was probably compiled for speed, so C compiled with `-size` can come out smaller
  than the original without leaving anything out (Crazy Taxi `replayChangeControl` hand-written: 2,244 bytes against the original's
  2,818, equivalent on 45 cases covering 591 of 1,118 instructions).
- Dead end (Crazy Taxi, 2026-10-23): the flat form's self-copies of a frame slot (`*(unsigned int *)((int)stk + 60) = *(int *)((int)stk
  + 60);`, 2,147 in game functions, 600 in PutCourse) cost nothing: SHC drops them (PutCourse 5,044 -> 5,032 bytes without them).

- Directed cases poked the function's own constants (Crazy Taxi, 2026-10-24): a compared value traced back to a load from the
  function's literal pool (`mova` + `fmov.s`, `mov.l @(disp,pc)`) was treated as an input and poked (Psg_Execute -6.0 at 0C06DF74
  set to 1.0; 3 of 22 new cases there, 10 of 24 for PutCourse_CheckPiece). That changes the original only, since the C keeps its own
  copy of the constant, so a right C differs. `directed.apply` now refuses a source inside the function's range (tests/directed).
- A structure passed by value (Crazy Taxi, 2026-10-24): SHC puts it in the caller's outgoing stack area (copied there with
  `_quick_mvn` / `_quick_odd_mvn`), never in r4-r7. The checker counted it as an integer register (it compared r4, a leftover)
  and missed its stack words; it now counts it by its words (tests/structargs). The generator got both sides wrong: the
  caller copied the structure into its own frame and passed a register instead (`ptfn(0x5, a5)`), and the callee was given r4-r7
  as parameters it never reads. Fixed (2026-10-24): a block copy whose destination is the stack pointer, followed by a call at the
  same depth, passes `*(StkN *)(source)` by value; a function that reads only the caller's stack words takes one `StkN s`; the
  StkN typedefs head the file (cases `structargfn`, `stackreadfn` in tests/gen_equiv). Hand fixes: gdc_CourseStartLoadReq,
  kmiInitPAL, kmiInitNTSC, kmiSetVideoTimings(KmVideoTimings: 252 bytes), Start_Proposal(int, int, NLpoint3).
- Dead end (Crazy Taxi, 2026-10-24): tools/equiv.py is not safe to run several at once in one repo. Three in parallel (xargs -P 3)
  crashed on a missing build/equiv/<stem>.map and reported whole files "not compiled" (179 functions in one), files that pass when
  run alone. One run at a time; a full recheck of 1,220 files is a long job, not a quick one.
- Structure sizes on SH (Crazy Taxi, 2026-10-24): the checker first counted every field as 4 bytes, so `AngleR { short x, y, z; }`
  (Model_Put_Sprite3D's angle) came out 3 stack words instead of 2 and every caller was compared on a leftover word. It now sizes
  fields by type (char 1, short 2, int/float/pointer 4, double 8), aligns each to its size, rounds the structure to its largest
  alignment and then to words; an unknown field type counts as a word (tests/structargs: shorts, { char; short } = 1 word).
- Drawing time (Virtua Tennis, 2026-10-24): 117 of 799 functions timed out drawing cases (60 s each). The two loops that run the
  original on candidates (pick, grow in gen_drv.py) ran every candidate and up to 250 stale growth tries, at up to 1.3 s a run for a
  function whose runs hit the step cap. Now one deadline per function (GEN_DRAW_SECONDS, default 40) covers every attempt: the
  candidates stop at it once 12 have ended (what a function with a loop needs) and the growth stops at it, so the function keeps
  the cases found (tests/drawbudget). Of the 117, 49 also had a size in functions.txt shorter than their code (a branch past the
  listed end, tools/1-2-baseline/checksizes.py flags it): the simulator never saw them return, every run went to the cap. The size
  is data, corrected per function in that run; the splitter that writes the sizes is not fixed yet.
  Rerun of the timeouts (2026-10-24): the deadline did not hold. 22 of the first 43 drawn still timed out. 13 were short sizes the
  per-function correction had missed (vmsfs_init: 194 listed, 250 real; its own tail after the mid-body pool was called as another
  function 16,644 times): `checksizes.py --extend` lists 719 such entries in Virtua Tennis, so the whole list is applied (`--write`)
  in step 2 before any draw, never per function. 7 were wait loops on a word a callee sets (rankDispLoad waits for
  `*0x8C34A1F0 == 1` around fileLoadPoll): random cases end 2 or 3 of 40 at 2 s a run, and the rule "stop once 12 have ended"
  never fired, so every candidate ran (about 400 a function, 3 attempts) until the 60 s alarm. Now the deadline stops the drawing
  however few ended, later attempts are skipped and the rest goes to directed.rescue (read sequences for such words), and the
  deadline is two thirds of the function's limit, max(60, size/8) s times GEN_TIME_FACTOR, so a slow function that ends keeps the
  longer time Crazy Taxi gave its slow draws (GEN_TIME_FACTOR 5 to 15 on kmiStartRenderTextureEntry, exec_KyakuMain). A longer
  limit alone never converted a wait loop (Crazy Taxi kmRenderTexture, ExecArrow, kyakuTaskExec timed out at 12x and 15x).
  Open: a loop that waits for a callee to return a value (emotFaceReset, entryPickRandomChara until -1): past the case's 48
  scripted results every call returns 0, so it never ends; rescue flips pokes and reads, not call results.
- Phantom parameters (Crazy Taxi, 2026-10-24): the flat form took every r4-r7 and fr4-fr11 the function mentions as a parameter,
  and the liveness behind it counted every call as reading r4-r7 and fr4-fr11. A function that sets its callee's argument
  registers itself (Start_Fog, gdc_SpriteFreeMenu, hudDrawTime) got a4-a7, and its callers were compared on leftover registers.
  Now only registers live at entry are parameters, and a call reads the arguments its callee takes (its code's arity or its
  proven definition; the block copy and division helpers their own registers; an unknown callee still all of them). Case
  `phantomfn` in tests/gen_equiv runs in both forms: the flat form wrote (int a4, int a5, int a6), now (void).
- Report stages (Virtua Tennis, 2026-10-24): tools/5-generated/remaining.py counted a function at the first step it had not passed,
  but a reason the generator gives for not reading a function is in its own words ("cannot read: arg gap"), so the rule's
  fall-through put every one under "Written C with errors": 172 functions (118,072 bytes), none of them with C. The stage rule is now
  a function (stage) whose fall-through is "Not written C"; only C the generator wrote and could not finish is past that step
  (tests/remaining).
- Lost register saves (Crazy Taxi, 2026-10-24): the build from C froze after loading the save. The optimizing link
  (optlnksh -optimize=...,register,...) drops a function's saves of r8-r14 when it believes it sees every caller; the original's
  pointer tables (task callbacks, interrupt hooks) are rewritten after the link (relocasm.py), so it does not see those callers.
  vmuExit as compiled saves r14 (MOV.L R14,@-R15 ... MOV.L @R15+,R14), as linked it does not. 609 functions, windowEnterStep and
  SetScreen on the path after the load among them. The checker never saw it: sh4sim leaves every stack store and the final r8-r14
  out of the comparison, and r15_balanced is read by no tool. Now OPTIMIZE has no register item: every function keeps the saves the
  compiler wrote (the compiler's assembly of all 239 build units against the linked game, 1,224 functions). Ruled out on the way, with the
  real save run in the simulator: buAnalyzeBackupFileImage, buCalcCRC (11,312 bytes) and SetTotalRecords give the same memory in
  the original and the build. Flycast GDB software breakpoints never fired (0 hits, placed before or after the game loads, both
  address forms, dynarec on or off): not a tool to rely on here.
