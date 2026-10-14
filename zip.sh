#!/usr/bin/env bash
# zip.sh: build dist/dc-decomp-kickoff.zip, the installable skill (one folder: SKILL.md, scripts/,
# template/, references/), from every file here git does not ignore. Upload it to Claude as a skill.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p dist
python3 - <<'PY'
import subprocess, zipfile
files = [f for f in subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"]).decode().split("\0")
         if f and not f.startswith("dist/") and f != "zip.sh"]
with zipfile.ZipFile("dist/dc-decomp-kickoff.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for f in files:
        if f != "VERSION":
            z.write(f, "dc-decomp-kickoff/" + f)
    # the version this zip is: the tag, or <last tag>+<commit> for a dev build (references/upgrade.md)
    v = subprocess.run(["git", "describe", "--tags", "--exact-match"], capture_output=True, text=True).stdout.strip()
    if not v:
        v = subprocess.check_output(["git", "describe", "--tags", "--abbrev=0"]).decode().strip() + "+" + \
            subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).decode().strip()
    z.writestr("dc-decomp-kickoff/VERSION", v + "\n")
print("%d files" % len(files))
PY
echo "Upload this to Claude as a skill: $PWD/dist/dc-decomp-kickoff.zip"
