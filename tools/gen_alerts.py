#!/usr/bin/env python3
"""Regenerate tools/stock_alerts.txt from the installed SC2 game data.

Every alert id the stock game can raise inside this map's dependency chain.
The map silences all of them at init and defines its own, because a
Lobotomy Corporation shift has nothing to say with "your forces are under
attack" -- and an alert nobody chose is worse than no alert, since the ones
that matter here are the ones we will be putting there.

Only the mods this map actually depends on are read. An alert id from a mod
that is not loaded cannot fire, and passing it to UISetAlertTypeVisible would
be asking the engine about something that does not exist.

Run this only when the dependency set or the reference data changes. The
output is committed so the build has no dependency on ~/SC2GameData/.
"""

import pathlib
import re
import sys
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "tools" / "stock_alerts.txt"
DATA = pathlib.Path.home() / "SC2GameData"

# Read from the map's DocumentHeader: Void (Mod) and Liberty (Campaign). Void
# pulls swarm and liberty behind it, and everything sits on core.
SOURCES = [
    "mods/core.sc2mod/base.sc2data/GameData/AlertData.xml",
    "mods/liberty.sc2mod/base.sc2data/GameData/AlertData.xml",
    "mods/swarm.sc2mod/base.sc2data/GameData/AlertData.xml",
    "mods/void.sc2mod/base.sc2data/GameData/AlertData.xml",
    "campaigns/liberty.sc2campaign/base.sc2data/GameData/AlertData.xml",
]

PREFIX = "Lob_"

GALAXY = ROOT / "src" / "galaxy" / "03_alerts_gen.galaxy"

HEADER = """//--------------------------------------------------------------------------------------------------
// GENERATED FILE -- DO NOT EDIT.
//
// Built from tools/stock_alerts.txt by tools/gen_alerts.py.
// To refresh the list from the game data, run that script directly.
//
// Every alert id the stock game can raise in this map's dependency chain.
// 04_alerts.galaxy switches them off; this file only knows their names.
//--------------------------------------------------------------------------------------------------

"""


def generate() -> list[str]:
    """Emit the id table from the committed list.

    Reads the text file rather than the game data on purpose: the build has to
    work on a machine that has no SC2 installed, and the list only changes when
    the map's dependencies do.
    """
    ids = [line.strip() for line in OUT.read_text(encoding="utf-8").splitlines() if line.strip()]

    out = [HEADER]
    out.append(f"const int c_stockAlertCount = {len(ids)};\n")
    out.append(f"string[{len(ids)}] gvg_stockAlert;\n\n")
    out.append("void AlertsGen_Init () {\n")
    out.extend(f'    gvg_stockAlert[{i}] = "{a}";\n' for i, a in enumerate(ids))
    out.append("}\n")

    GALAXY.write_text("".join(out), encoding="utf-8")
    return ids


def main() -> int:
    if not DATA.is_dir():
        print(f"error: no game data at {DATA}", file=sys.stderr)
        return 1

    ids: list[str] = []
    seen = set()
    for rel in SOURCES:
        path = DATA / rel
        if not path.is_file():
            print(f"  skipped (absent): {rel}", file=sys.stderr)
            continue
        for alert in ET.parse(path).getroot().iter("CAlert"):
            # The root default entry has no id and is not an alert anybody can
            # raise; it is the thing every other entry inherits from.
            aid = alert.get("id", "")
            if not aid or aid.startswith(PREFIX) or aid in seen:
                continue
            seen.add(aid)
            ids.append(aid)

    if not ids:
        print("error: no alerts found", file=sys.stderr)
        return 1

    OUT.write_text("\n".join(sorted(ids)) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(ids)} stock alert ids")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
