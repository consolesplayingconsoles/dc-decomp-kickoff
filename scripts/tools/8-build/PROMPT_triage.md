# Prompt: a build from C that stopped (step 8)

Give this to an agent with the build's last lines pasted in.

---

The build from C (`make c` / `make disc`) stopped. Find why and say what fixes it; change nothing unless told to.

1. Read the build's own message first: the last lines name the tool that stopped (`retcheck`, `protocheck`, `cbuild`, `fit`,
   `audit`, `movecheck`, a missing file). Find that tool in `tools/` and read the check that fired. Do not guess from earlier
   builds.
2. A missing file or folder: check the path the tool builds against this repo's `tools/` layout (a tool copied from a newer or
   older skill may name a folder this repo does not have).
3. `fit` over the limit: the number is bytes past `layout.txt`'s `fixed`. Only the `game` region's C is in the image; the
   `keep` regions are original bytes. Compare with the previous build's figure before calling anything a regression.
4. A check on a function (wrong result register, dropped arguments, a call into the middle of a function, a stale address):
   name the function and its file, run `python3 -I tools/sim/equiv.py <unit> <function>`, and say which step it goes back to
   (step 5 regenerate, step 6 by hand, step 2 `functions.txt`).
5. Never edit `layout.txt`, `functions.txt`, the tools or the C to make a check pass: report what it found and the fix it needs.

Report: the stopping tool and line, the cause in two sentences, the fix and which step it belongs to, and whether a rebuild is
needed after it.
