#!/usr/bin/env python3
"""Backwards compatibility of the map tool's readers. Stdlib only.

    check.py                          compare the readers' output on the synthetic inputs (emit.py) with golden.json
    check.py --update                 accept new entries (a new reader or a new input): golden.json gains them
    check.py --update --breaking vX.Y accept changed or removed entries, the version that brings the change recorded

Maps made by an older version must still read: what the readers found before, they still find. So an existing entry
may not change or disappear; new ones may appear. A deliberate break needs `--breaking <version>`, which records it in
golden.json (`breaking`): a viewer must then have a reader from that version on (its own check reads this list)."""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GOLDEN = os.path.join(HERE, "golden.json")


def current():
    out = subprocess.run([sys.executable, os.path.join(HERE, "emit.py")], stdout=subprocess.PIPE, check=True).stdout
    return json.loads(out.decode("utf-8"))


def main():
    args = sys.argv[1:]
    update = "--update" in args
    breaking = args[args.index("--breaking") + 1] if "--breaking" in args else ""
    if breaking and not re.match(r"^v\d+\.\d+$", breaking):
        sys.exit("[ERROR] --breaking takes a version like v0.7")
    cases = current()
    golden = json.load(open(GOLDEN)) if os.path.exists(GOLDEN) else {"breaking": [], "cases": {}}
    old = golden["cases"]
    removed = sorted(k for k in old if k not in cases)
    changed = sorted(k for k in old if k in cases and old[k] != cases[k])
    added = sorted(k for k in cases if k not in old)
    if not (removed or changed or added):
        print("[compat] ok: %d cases, the readers find what they found before" % len(cases))
        return
    for k in removed:
        print("[compat] removed: " + k)
    for k in changed:
        print("[compat] changed: %s\n    was %s\n    now %s" % (k, json.dumps(old[k]), json.dumps(cases[k])))
    for k in added:
        print("[compat] new:     " + k)
    if (removed or changed) and not breaking:
        sys.exit("[compat] FAILED: a reader's output changed, which breaks maps made by earlier versions.\n"
                 "  If it is a mistake, fix the reader. If it is deliberate: check.py --update --breaking <version>\n"
                 "  (and the viewer needs a reader from that version on).")
    if not update:
        sys.exit("[compat] FAILED: new entries are not in golden.json yet: run check.py --update")
    if breaking and breaking not in golden["breaking"]:
        golden["breaking"].append(breaking)
    golden["cases"] = cases
    with open(GOLDEN, "w") as f:
        json.dump(golden, f, indent=1, sort_keys=True)
        f.write("\n")
    print("[compat] golden.json updated" + (" (breaking from %s)" % breaking if breaking else ""))


if __name__ == "__main__":
    main()
