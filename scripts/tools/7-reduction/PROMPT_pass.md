# Prompt: try a rewrite pass, then run it (step 7)

For a new pass in `tools/5-generated/gen_equiv/rewrites.py` (one function of text in, text out), or an existing one not yet run
on this repo. Give this to an agent with `<pass>` filled in.

---

Run the shrink pass `<pass>` on this repo's game code and count what it really gains.

1. Only the code the console build compiles counts: `layout.txt`'s `game` region, outside every `keep` region. Library and data
   functions stay the original bytes, so their C never reaches the image: leave them out of every list and every total.
2. Count first: how many game functions have the shape the pass changes (call the pass on each unit's text and compare), and
   which units hold them. No compile yet.
3. Run it in the repo: check first that nothing else runs there (no build, no other shrink), then
   `nice -n 19 python3 -I tools/7-reduction/shrink.py --passes <pass> <units>` on the units with the shape, one process, and give
   the user `tail -f <repo>/build/shrink.log`. The tool keeps a function only when it compiles smaller and still proves, and
   restores the old C otherwise.
4. Read `build/shrink.log`: functions smaller and proven, bytes saved, functions not smaller, and every `DIFFERS` or failure.
   A function whose OLD C also fails ("NOT EQUIVALENT after the restore") is a broken function already in the repo: list it.
5. Re-prove at the bar: for every function the pass made smaller whose proof ran under 70-80% of its instructions, raise
   coverage on the OLD C first with `PROMPT_prove.md` (beside the step 6 tools), then prove the new C on those cases. Put the
   old C back for any that do not prove at the bar, and report them as unproven, not as savings. This is the only prompt this
   one uses, once per function, and `PROMPT_prove.md` uses none.


Rules: no build, no git, never kill a process you did not start, never change the generator, checker or simulator while a pass
runs (its proofs are stamped with their hashes).

Report: one numbered table: units and functions with the shape, functions kept, bytes saved, functions put back after the
re-proof, the broken functions found.
