# Names from a later port that kept its symbols

Many Dreamcast games were later ported (Android, iOS, PC, consoles) from the same source. A port
built as a shared library usually keeps its symbol table: every exported function and global by
its original name, C++-mangled with the argument types. The code is a different CPU and compiler,
so nothing matches byte for byte, but the program is the same: same strings, same constants, same
calls in the same order. That is enough to pair a large share of the Dreamcast functions with their
real names.

On one game this named about a fifth of the functions the decomp had not named yet
(`evidence.md`). Ask the user for the port's file; never fetch an APK or game build yourself.

## Check for symbols first (a minute)

A port helps only if it kept names. Before any pairing: a Windows `.exe` with an empty export
table, no debug directory (or one pointing at a `.pdb` that did not ship) and no game class names
has none; a GameCube disc without a `.map` file and with stripped `.dol`s has none; extra
executables on a disc are often bundled applications (a web browser), not the game. A port of the
arcade original rather than of the Dreamcast version shares no code with it. Without symbols, a
port is still a reading reference (x86 decompiles more readably), not a naming source.

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
  reading the SH-4 code. Signature names are seeds too, so a wrong one spreads: `validate.py`
  lists short signature names with no same-family name nearby, to check before trusting them.
- **Calls through the PLT.** A shared library calls its own exported functions through PLT stubs:
  resolve a stub to the function it forwards to (`getThunkedFunction`), or every call list is
  empty and nothing propagates.
- **Compiler runtime helpers.** SH-4 calls helpers for division, modulo and struct copies that
  ARM does inline; they flood the Dreamcast call lists and break call-order alignment. List their
  range in `RUNTIME_SKIP` (typically the unnamed functions between the game code and the C
  library).
- **The port's own code.** Pair only the port's original game functions (free functions
  `_Z<digit>...` or plain C names), never its C++ classes: a string can live in a port-only class
  that merely calls the original, and the original would get the class method's name.
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
- **Callers through the PLT, when reading by hand.** In the port's Ghidra project, an xref on an
  exported function finds only its stub. `Query.java callers <addr>` lists the functions that call
  it directly or through any stub.
- **Function-pointer tables pair whole families.** State machines keep their handlers in
  function-pointer arrays (globals, or initialised locals whose template sits in the constant
  data). In the shared library each entry is an `R_AARCH64_RELATIVE` relocation, so
  `objdump -R` gives a table's entries in order; pairing them with the Dreamcast table, entry by
  entry, names the whole family at once.
- **Lining up a struct between builds.** The port keeps Dreamcast addresses as plain 32-bit
  constants (motion and model pointers, loaded data addresses): exact anchors for a field's offset.
  Offsets agree on both sides up to the first pointer field; each pointer the 64-bit port widens
  shifts everything after it by +4. Walking a record that way maps it quickly.

Expect a few wrong names among the applied ones: say so in the docs, and prefer a name proven by
reading the code over the matcher's.
