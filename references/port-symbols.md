# Names from a later port that kept its symbols

Many Dreamcast games were later ported (Android, iOS, PC, consoles) from the same source. A port
built as a shared library usually keeps its symbol table: every exported function and global by
its original name, C++-mangled with the argument types. The code is a different CPU and compiler,
so nothing matches byte for byte, but the program is the same: same strings, same constants, same
calls in the same order. That is enough to pair a large share of the Dreamcast functions with their
real names.

**Crazy Taxi (Europe)** against Crazy Taxi Classic 6.0 for Android (`lib/arm64-v8a/libgl2jni.so`,
from the user's own APK): about 980 original game functions and 470 of Sega's Naomi library named
in the port; 310 Dreamcast functions and 29 globals paired, 257 of them new names for the decomp;
all functions named in the decomp went from 20% to 31% (game code alone: 23% after). Ask the user for the port's file;
never fetch an APK or game build yourself.

## Steps (scripts in `scripts/port/`, `scripts/ghidra/ExportFeatures.java`)

1. Get the library: an `.apk`/`.xapk` is a zip; the native code is `lib/<abi>/*.so` (a split
   `.xapk` keeps it in `config.<abi>.apk`). `nm -D --defined-only` should list the game's names.
2. Import the library into Ghidra (headless, `-import`, default ELF loader: about 15 minutes for
   9 MB, one Ghidra job at a time) and run `ExportFeatures.java` on it and on the decomp's
   Dreamcast project (`-process 1ST_READ.BIN -noanalysis -readOnly`): `port_features.jsonl`,
   `dc_features.jsonl` in one work folder.
3. In that folder, with `PORT_LIB`, `DECOMP` (and `RUNTIME_SKIP`, `DROP_GLOBALS` once known) set
   (see `portcfg.py`), loop until nothing changes:
   ```
   python3 match.py && python3 validate.py && python3 gmatch.py
   ```
   `match.py` pairs functions (`pairs.tsv`), `validate.py` rejects impossible pairs
   (`accepted.tsv`), `gmatch.py` pairs globals (`globals.tsv`), which the next `match.py` uses.
4. Apply `accepted.tsv` to `functions.txt` (only for `FUN_` entries, never overwriting a name
   given by reading the code: record the original next to it in the docs instead) and
   `globals.tsv` to `globals.txt`. Re-split, build: still `MATCH`. Check a sample by hand.

## How pairing works, and what went wrong on the way

- **Seeds**: names already shared (the SDK and Naomi library names the decomp has), a string only
  one function uses on each side, two rare constants shared, and `seeds.tsv` for pairs proven by
  reading the SH-4 code.
- **Calls through the PLT.** A shared library calls its own exported functions through PLT stubs:
  resolve a stub to the function it forwards to (`getThunkedFunction`), or every call list is
  empty and nothing propagates.
- **Compiler runtime helpers.** SH-4 calls helpers for division, modulo and struct copies that
  ARM does inline; they flood the Dreamcast call lists and break call-order alignment. List their
  range in `RUNTIME_SKIP` (Crazy Taxi: the unnamed functions between the game code and the C
  library, `0x0C080E00-0x0C081700`).
- **The port's own code.** Pair only the port's original game functions (free functions
  `_Z<digit>...` or plain C names), never its C++ classes: a string can live in a port-only class
  that merely calls the original (Crazy Taxi: `gameInit` would have been named `Update`).
- **Inlining** breaks call order: the port inlined small Dreamcast functions (or the reverse).
  Pairing by shared neighbours (paired callers and callees, paired globals, rare constants) is
  what carries most of the propagation; call-order gaps only help locally.
- **Look-alike utilities** (matrix push/pop/translate/rotate) share almost the same neighbours and
  got crossed. Code size breaks some ties (the port/Dreamcast size ratio is measured on the seeds,
  1.5-1.6 for ARM64), but the reliable fix is proving the busy ones by reading the code into
  `seeds.tsv` and keeping neighbour pairing off functions with over 30 callers.
- **Validation by signature.** A Dreamcast function that reads more of r4-r7 (the first four
  integer arguments) than the port's signature has integer parameters is not that function.
  Reading fewer proves nothing. It caught real mistakes (a 4-argument setter paired with a
  1-argument function).
- **Globals** sit behind the GOT in a shared library (`R_AARCH64_GLOB_DAT` relocations name them);
  file-local statics have no name at all. A buffer address used as a value (a pointer passed
  around) pairs with a variable by mistake: put such addresses in `DROP_GLOBALS`. A name that two
  addresses claim is dropped.
- macOS `c++filt` only demangles `_Z...` with `-n` (it expects Mach-O's extra underscore).

Expect a few wrong names among the applied ones: say so in the docs, and prefer a name proven by
reading the code over the matcher's.
