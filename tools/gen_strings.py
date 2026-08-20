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

And one check on the editor's half of the file, which the build otherwise
copies through without looking: check_shadow, below.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src" / "strings"
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


def read_all() -> tuple:
    """Every *.enUS.txt under src/strings/, merged, with the file each key came
    from so an error can name it."""
    table, origin = {}, {}
    for p in sorted(SRC_DIR.glob("*.enUS.txt")) + sorted(SRC_DIR.glob("enUS.txt")):
        for k, v in read_table(p).items():
            if k in table:
                raise SystemExit(f"{p.name}: {k!r} is already defined in {origin[k]}")
            table[k], origin[k] = v, p.name
    return table, origin


ID_RE = re.compile(r'\bid="([^"]+)"')

# Namespaces where a value is a DISPLAY NAME -- something a player reads. A
# player never reads an object id, so an id turning up on the right-hand side of
# one of these is the editor having filled a blank in, not a name anybody chose.
NAME_SPACES = ("Unit/", "Abil/", "Weapon/", "Behavior/", "Button/", "Effect/",
               "Upgrade/", "Actor/", "Requirement/", "Validator/")


def check_shadow(merged: dict) -> bool:
    """Refuse a display name whose value is some OTHER object's id.

    This catches one specific accident with a blast radius far wider than it
    looks. Point a new unit's <Name> at a key that already belongs to a STOCK
    object -- <Name value="Unit/Name/Zergling"/>, say, which is what copying a
    Zergling and forgetting to rename gets you -- and the editor helpfully
    writes that key into the MAP's GameStrings.txt with the new unit's id as the
    value. From then on the map's copy shadows Blizzard's for every zergling in
    the game, and 50_waves spawns zerglings. Nothing errors. The name is just
    wrong, everywhere, and the file that says so is the one file the build
    copies through untouched.

    The rule is narrow on purpose: the value has to be an id THIS MAP defines,
    and not the key's own id. Renaming a stock object on purpose is ordinary and
    stays legal -- ContainGate and DestructibleGateDiagonalBLUR are both renamed
    stock and both have real names on the right. And Unit/Name/Lob_SCV_Worker=
    Lob_SCV_Worker is a placeholder, not a mistake, so a key naming itself is
    left alone.
    """
    ids = set()
    for path in sorted((ROOT / "LobotomyShiphold.SC2Map" / "Base.SC2Data"
                        / "GameData").glob("*.xml")):
        ids.update(ID_RE.findall(path.read_text(encoding="utf-8")))

    bad = []
    for key in sorted(merged):
        if not key.startswith(NAME_SPACES):
            continue
        value = merged[key]
        if value in ids and value != key.rsplit("/", 1)[-1]:
            bad.append((key, value))

    if bad:
        print(f"  ! {len(bad)} display name(s) set to an object id:")
        for key, value in bad:
            print(f"    {key}={value}")
        print("    A <Name> pointing at another object's string key makes the")
        print("    map shadow that name everywhere. Point it at its own key.")
    return bool(bad)


def main() -> int:
    ours, origin = read_all()

    bad = [k for k in ours if not k.startswith(NAMESPACE)]
    if bad:
        raise SystemExit(
            f"src/strings/ may only define {NAMESPACE}* keys; the rest of "
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
            f"nothing at all in game. Add them to src/strings/enUS.txt:\n"
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
    from build_galaxy import write_map_file
    write_map_file(OUT, BOM + "".join(f"{k}={merged[k]}\n" for k in sorted(merged)))

    print(f"generated {OUT.relative_to(ROOT)}")
    print(f"  {len(ours)} Lob/ strings, {len(theirs)} left to the editor")

    if check_shadow(merged):
        return 1

    unused = sorted(k for k in ours
                    if k not in refs and not any(k.startswith(p) for p in prefixes))
    if unused:
        print(f"  ! {len(unused)} defined but never referenced:")
        for k in unused:
            print(f"    {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
