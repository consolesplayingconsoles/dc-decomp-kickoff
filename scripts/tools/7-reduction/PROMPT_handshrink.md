# Prompt: hand-shrink one function (step 7)

Candidates:  lists the functions whose original repeats one run of instructions many times.
For the functions no pass or regeneration gets near their original size: the generator's C of an unrolled loop, a lift of code
built without optimisation, a block written once per path. Give this to an agent with `<function>`, `<unit>` and the sizes filled in.

---

Write a smaller C version of ONE function of this decomp and prove it. Function: `<function>` (original `<orig>` bytes, current C
`<c>` bytes), unit `<unit>`. Commands from the repo root, always `nice -n 19`, one compile at a time.

1. Understand it first: `python3 -I tools/sim/shdis.py --func <function>` and the current C. Decode every pool constant. Look for
   what makes it big: N copies of one block that differ in constants (one loop), values kept in a frame array (locals), a tail
   written once per path, a result threaded through every exit of a function whose callers never read it.
2. Work in a scratch copy, never in `src/`: a folder under `build/manual/proof_<function>/` holding a copy of `<unit>` at the same
   path, the rest of `src/` and every other top-level entry symlinked, and its own `tests/`, `state/`, `build/`. Prove there:
   `python3 -I tools/sim/equiv.py <unit> <function>`.
3. Coverage bar: hand-written C is accepted only when its cases run at least 70-80% of the function's instructions (aim for all).
   Raise coverage on the OLD C first (`PROMPT_prove.md` beside the step 6 tools says how), so you know the cases are good; then
   prove the new C on the same cases. If the old C fails your better cases, say so: that is a finding.
4. Size: `python3 -I -c "import sys; sys.path.insert(0,'tools'); import toolpath, sizes; print(sizes.unit_sizes('<unit>'))"`
   in the scratch folder.
5. Mark the definition `/* manual: <what it does>; <cases>, <N of M> instructions */` right above it: the passes and the
   generator then leave it alone.
6. Keep the original's order of calls and memory accesses, and pass argument registers the original leaves untouched as they
   came. A device region is compared on the order of its reads.

Rules: write only in the scratch folder and one notes file `build/manual/notes_<function>.txt` (patterns used, what went wrong).
No new scripts. Never kill a process you did not start. No build, no git. If you cannot reach the bar with a smaller version,
stop and say where it stands.

Report: original / old C / new C bytes, the equiv line, the old C's verdict on the same cases, the uncovered instructions and
why, the paths of the proven unit copy and its case file, and the patterns worth a generator rule.
