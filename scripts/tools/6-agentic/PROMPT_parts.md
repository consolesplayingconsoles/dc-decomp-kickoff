# Prompt: an outlier function, written in parts (step 6)

Give this to an agent, with `<function>` filled in. It is self-contained; the agent needs no other briefing.

---

Write and prove the C of ONE function far larger than the rest of this decomp (several KB, over every size band, or a timeout of the
generator on its own). Never run the generator or any tool on the whole function without a bound: a whole run blocks the machine for
hours and ends in a timeout.

Function: `<function>`. Run every command from the repo root, always with `nice -n 19`, one compile at a time.

1. Map it: `python3 -I tools/6-agentic/parts.py map <function>` (state/parts/<function>/parts.txt: parts of at most 600
   instructions, cut along the dominator tree, the glue between them and the shared exit). Read the map against the disassembly
   (`python3 -I tools/sim/shdis.py --func <function>`): find the dispatch (a switch on a field of the argument, a chain of compares),
   and the sections that repeat with the same shape and different constants. Write down, per section, what it reads and writes, its
   loop bounds and its constants. Code compiled without optimization keeps every variable in its own frame slot: the stack is not
   compared by the check, so the C uses plain variables and loops.
2. Read the parts: `python3 -I tools/6-agentic/parts.py read <function>` (state/parts/<function>/<part>.c). The generator's C of a part
   is register-level, with the parent's frame words as parameters; use it to check the arithmetic of a section, not to join from. A
   part not read (a jump to the shared exit, a register an earlier part set) is read by hand from the disassembly.
3. Write the function by hand, in one new file `src/<function>.c`: one frame, the dispatch, the sections in order, the exits the
   compiler shared written once. Repeated sections as one loop or macro with their constants, when the code allows it. A static
   helper function is not allowed (one function per entry). Mark it `/* manual: written in parts (tools/6-agentic/parts.py) */`
   above the definition.
4. Prove it: `python3 -I tools/5-generated/gen_equiv/__main__.py --draw src/<function>.c`, then
   `python3 -I tools/sim/equiv.py src/<function>.c`. Then raise coverage as in PROMPT_prove.md (fuzzcases, casesearch, and
   hand-written cases with every value of the dispatch field, so that every section runs). The bar: 70-80% of the instructions or
   more, no section left unrun. A DIFFERS names the case and the first differing write: find the section it belongs to and fix it.
5. If the function had generated C before, take that definition out of its batch file only after the new one is proven, and run
   `python3 -I tools/5-generated/audit_equivalent.py` and `python3 -I tools/8-build/retcheck.py` (both must be clean).

Rules: write nothing but `src/<function>.c`, its case file, and state/parts/. No new scripts in the repo. No change to functions.txt
(a part is not an entry: the scratch copy under state/parts/ has its own). Never kill a process you did not start. No build, no git.

Report: the map (dispatch, sections, which repeat), the parts read by the generator and by hand, the final equiv line, and the
instructions still not run and why. Short.
