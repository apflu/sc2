#!/usr/bin/env python3
"""Regenerate tools/known_calls.txt from the installed SC2 game data.

Every function a hand-written Galaxy script is allowed to call that this
project does not define itself. That is the natives plus the trigger
libraries -- NOT the campaign maps' own scripts, which a custom map cannot
reach and which would only widen the list enough to swallow real typos.

Run this only when the reference data changes. The output is committed so the
build has no dependency on ~/SC2GameData/ being present.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "tools" / "known_calls.txt"
DATA = pathlib.Path.home() / "SC2GameData" / "mods"

# A declaration is "<type> <name> (", optionally prefixed with `native`. That
# shape also matches a call sitting alone on a line after a cast, so the list
# errs wide -- which is the safe direction for a list of things we permit.
DECL = re.compile(
    r"^\s*(?:native\s+)?(?:const\s+)?[A-Za-z_]\w*\s*(?:\[\s*\d*\s*\])?\s+(\w+)\s*\(", re.M)

KEYWORDS = {"if", "while", "for", "return", "else", "do", "switch", "break", "continue"}


def main() -> int:
    if not DATA.is_dir():
        print(f"error: no game data at {DATA}", file=sys.stderr)
        return 1

    names: set[str] = set()
    files = 0
    for path in DATA.glob("*/base.sc2data/TriggerLibs/**/*.galaxy"):
        files += 1
        text = re.sub(r"//[^\n]*", "", path.read_text(encoding="utf-8", errors="replace"))
        names.update(DECL.findall(text))
    names -= KEYWORDS

    OUT.write_text("\n".join(sorted(names)) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(names)} names from {files} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
