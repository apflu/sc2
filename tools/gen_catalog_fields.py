#!/usr/bin/env python3
"""Regenerate tools/catalog_fields.txt from the installed SC2 game data.

Every (catalog class, parent element, child element) triple that Blizzard's own
GameData uses. That is enough to catch the mistake this exists for: a real field
name put in the wrong place.

    <CBehaviorBuff>
        <Modification>
            <DamageResponse .../>     <-- real field, wrong parent

The editor's only complaint about that is "Unable to find field DamageResponse",
printed to a log nobody reads until something is already broken, and the field
itself is simply ignored at runtime. DamageResponse belongs directly under the
behavior; DeathResponse, next to it in every way that looks like it should
matter, belongs inside Modification. There is no way to know that but to look.

Run this only when the reference data changes. The output is committed so the
build has no dependency on ~/SC2GameData/ being present.
"""

import pathlib
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "tools" / "catalog_fields.txt"
DATA = pathlib.Path.home() / "SC2GameData"


def walk(cls: str, el: ET.Element, out: set[str]) -> None:
    for child in el:
        if not isinstance(child.tag, str):
            continue
        out.add(f"{cls}\t{el.tag}\t{child.tag}")
        walk(cls, child, out)


def main() -> int:
    if not DATA.is_dir():
        print(f"error: no game data at {DATA}", file=sys.stderr)
        return 1

    triples: set[str] = set()
    files = 0
    globs = ("mods/*/base.sc2data/GameData/*.xml",
             "campaigns/*/base.sc2data/GameData/*.xml")
    for pattern in globs:
        for path in DATA.glob(pattern):
            try:
                root = ET.parse(path).getroot()
            except ET.ParseError:
                continue
            files += 1
            for entry in root:
                if not isinstance(entry.tag, str) or not entry.tag.startswith("C"):
                    continue
                walk(entry.tag, entry, triples)

    OUT.write_text("\n".join(sorted(triples)) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(triples)} triples from {files} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
