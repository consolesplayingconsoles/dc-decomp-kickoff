# Code overlays

Some games keep code in files on the disc that are loaded at a fixed address (Sonic Adventure: PRS-compressed stage, boss, event and Chao
code). A project with `overlays.tsv` in the repo root has them; one without it is unaffected (`setup.sh`, `tools/progress.py` and the
ignore list only look at the overlays when the file is there).

## Layout

- `overlays.tsv`: every disc file with code, tab separated: `name`, load address `base`, hash, `status` (the reason when a file is out of scope).
  The one place for an overlay's address: `python3 tools/overlay/ovtsv.py base <name>`. `tools/overlay/survey.py <disc.gdi> > overlays.tsv`
  writes a first one.
- `overlays/<name>/`: `functions.txt`, `globals.txt` and `symbols.local.txt` of one overlay (committed). `setup.sh` adds the decompressed
  image `<name>.bin`, `asm/` and `objects.txt` (`tools/overlay/setup_overlays.py`; never committed).
- The C units of the overlays are stored once (`overlays/src/<unit>.c`, or a source tree's own folders). `overlays/units.tsv` (overlay, unit,
  start, end, header options) says which overlays have each unit and at what range: the same code sits at a different address in each. The
  build writes `overlays/<name>/src/` from those rows (`tools/overlay/place_units.py`; generated, git-ignored). A file is rewritten only when
  its text changes, so a build recompiles only what changed.

## Building

`bash build.sh --overlay <name>` is the same build as `bash build.sh`, run in the overlay's folder: its asm, its C units (`shc`,
`fill.py`, `units.py`), linked at its base and compared with its decompressed image. A unit's outside names come from the overlay's
`functions.txt`, `globals.txt` and `symbols.local.txt`, then from the main executable's (`tools/overlay/link_defs.py`). `bash
build_overlays.sh [name ...]` runs it for every overlay (`JOBS=<n>`: n at a time). The match compares decompressed images; recompressing
to the disc's exact bytes is not done. `shc` cannot open its temp files under a long path ("Cannot open internal file"), so an overlay's
build gives it a short one of its own (`/tmp/shc_<name>`).

## Tools on an overlay

`bash tools/overlay/in.sh <name> <tool> <args>` runs a shared tool in the overlay's folder (`shdis.py --func X`, `equiv.py src/x.c`): it
writes the image as `1ST_READ.BIN`, `BASE`, the units and a `symbols.txt` with the main executable's names there, and puts the compiler's
runtime helpers of the main executable in the simulator's memory (`SH4SIM_ALSO`, set only by this script, so no other run is affected).

## Function lists and shared code

- `tools/overlay/analyze.py <image> <base hex> [--main] > functions.txt` is a reachability pass. Boundaries never change the rebuilt bytes,
  but a wrong one blocks a C unit: check them before writing C. A typical fault is a boundary on the delay slot of the previous function's `rts`.
- Much code is linked into several images. A unit matched once is carried to every copy: `python3 tools/overlay/carry_unit.py <overlay>
  <unit> [overlay[@address] ...]` finds each copy (masked words equal), moves the unit's boundaries, reads that overlay's globals from its own
  pools, adds the row to `overlays/units.tsv` and keeps it only if `build.sh --overlay` matches with the unit linked. Units of only a few
  words match everywhere by chance: such hits are not copies.
- `python3 tools/progress.py` ends with the overlays' own total (`tools/overlay/progress.py`); the main metric stays the main executable's.
