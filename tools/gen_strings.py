#!/usr/bin/env python3
"""Merge src/strings/enUS.txt into the map's enUS GameStrings.txt.

The build owns the Lob/ namespace in the enUS file and nothing else in it. Every
other line -- the catalog strings the data editor writes, Abil/Name, Button/
Tooltip and the rest -- is read back and written out untouched, so this can run
after any editor save without eating anybody's work.

Other locales are never written. A zhCN.SC2Data/LocalizedData/GameStrings.txt is
the translator's file and the build has no opinion about it; adding one is the
whole of adding a language.

Two checks, because the failure mode this replaces is silent. A Lob/ key
referenced from Galaxy but missing here renders as nothing at all in game -- an
empty objective, a blank tooltip -- which looks like a layout bug and is not
one. So:

    referenced but not defined   ->  build error
    defined but never referenced ->  warning, because a key can also be built by
                                     concatenation and this cannot see that
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "strings" / "enUS.txt"
GALAXY = ROOT / "src" / "galaxy"
OUT = ROOT / "LobotomyShiphold.SC2Map" / "enUS.SC2Data" / "LocalizedData" / "GameStrings.txt"

NAMESPACE = "Lob/"
BOM = "﻿"

# Any Lob/ literal in the sources, not just the ones sitting inside a
# StringExternal call. A key is just as much a key when it is handed to
# Quest_Declare and read back out of a table three functions later, and a
# scanner that only understood the direct call would have reported thirty-six
# live quest titles as dead.
REF_RE = re.compile(r'"(' + "Lob/" + r'[^"]*)"')


def read_table(path: Path) -> dict:
    """key=value lines, ignoring blanks and # comments."""
    table = {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.lstrip(BOM)
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if "=" not in line:
            raise SystemExit(f"{path}:{n}: not a key=value line: {line!r}")
        key, value = line.split("=", 1)
        if key in table:
            raise SystemExit(f"{path}:{n}: duplicate key {key!r}")
        table[key] = value
    return table


def referenced_keys() -> dict:
    """Every Lob/ literal in the Galaxy sources, and the first place it appears."""
    found = {}
    for p in sorted(GALAXY.glob("*.galaxy")):
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for m in REF_RE.finditer(re.sub(r"//.*", "", line)):
                found.setdefault(m.group(1), f"{p.name}:{n}")
    return found


def main() -> int:
    ours = read_table(SRC)

    bad = [k for k in ours if not k.startswith(NAMESPACE)]
    if bad:
        raise SystemExit(
            f"{SRC.relative_to(ROOT)} may only define {NAMESPACE}* keys; the rest of "
            "GameStrings.txt belongs to the editor:\n"
            + "\n".join(f"  {k}" for k in sorted(bad)))

    # A literal that is not itself a key but is the start of one is a prefix
    # being concatenated with something computed -- "Lob/Dept/Name/" + the
    # Sephirot id. Those are legitimate and cannot be resolved from here, so
    # they are neither an error nor evidence that any particular key is used.
    refs = referenced_keys()
    prefixes = {k for k in refs
                if k not in ours and any(d.startswith(k) for d in ours)}

    missing = sorted(k for k in refs if k not in ours and k not in prefixes)
    if missing:
        raise SystemExit(
            "Galaxy references strings that are not defined -- these render as\n"
            f"nothing at all in game. Add them to {SRC.relative_to(ROOT)}:\n"
            + "\n".join(f"  {k}   ({refs[k]})" for k in missing))

    # Everything in the map file that is not ours, kept exactly as it was.
    theirs = {}
    if OUT.is_file():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            line = line.lstrip(BOM)
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if not key.startswith(NAMESPACE):
                theirs[key] = value

    merged = dict(theirs)
    merged.update(ours)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        BOM + "".join(f"{k}={merged[k]}\n" for k in sorted(merged)),
        encoding="utf-8")

    print(f"generated {OUT.relative_to(ROOT)}")
    print(f"  {len(ours)} Lob/ strings, {len(theirs)} left to the editor")

    unused = sorted(k for k in ours
                    if k not in refs and not any(k.startswith(p) for p in prefixes))
    if unused:
        print(f"  ! {len(unused)} defined but never referenced:")
        for k in unused:
            print(f"    {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
