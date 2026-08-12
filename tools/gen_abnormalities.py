#!/usr/bin/env python3
"""Generate the abnormality table from docs/usr/abnormality/*.md.

The design documents are the data source. That is not a shortcut -- it is the
answer to a question this project has been stuck on twice.

Three things need a per-abnormality NUMBER: the Qliphoth counter's default, the
work preference table, and residual management difficulty. Unit attributes are a
closed set of thirteen bare flags with no payload, so they cannot hold any of
it, and picking some unused CUnit field to smuggle a number through is exactly
the mistake the authoring contract warns against. A separate authored table
would work, but it would be a second place to maintain, and the first place
already exists and is already being written by hand for every abnormality.

So the doc is the table. A file at docs/usr/abnormality/<UnitId>.md declares an
abnormality, its filename is the unit id in UnitData.xml, and everything the
script needs is parsed out of prose that was going to be written anyway.

Parsing is deliberately forgiving. These files are written for people: the
tables come out of a wiki as ragged tab-separated text, sections appear in
different orders, and an early one may have no tables at all. Anything missing
comes out as a documented default and is reported at build time, so a gap is
visible rather than silently zero.

Output is src/galaxy/04_abno_gen.galaxy, committed like the other generated file.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs" / "usr" / "abnormality"
UNIT_DATA = ROOT / "LobotomyShiphold.SC2Map" / "Base.SC2Data" / "GameData" / "UnitData.xml"
OUT = ROOT / "src" / "galaxy" / "04_abno_gen.galaxy"

# Must match c_risk* in 06_risk.galaxy, and the attribute each grade lives in.
RISKS = ["ZAYIN", "TETH", "HE", "WAW", "ALEPH"]
RISK_ATTRIBUTE = {
    "ZAYIN": "Biological",
    "TETH": "Light",
    "HE": "Armored",
    "WAW": "Psionic",
    "ALEPH": "User1",
}

# Order must match c_work* in 14_work.galaxy.
WORKS = ["Instinct", "Insight", "Attachment", "Repression"]

# Stated in O-03-03's Details as applying to every abnormality by default.
DEFAULT_BOX_SPEED = 0.30
DEFAULT_COOLDOWN = 10.0
DEFAULT_MAX_BOX = 10

# A counter of X means "not applicable" -- the abnormality has no counter at all
# rather than a counter of zero, and it is a different thing from one that has
# run out.
COUNTER_NONE = -1

HEADER = """//--------------------------------------------------------------------------------------------------
// GENERATED FILE -- DO NOT EDIT.
//
// Built from docs/usr/abnormality/*.md by tools/gen_abnormalities.py.
// The design document is the data source; write the doc, rebuild, done.
//--------------------------------------------------------------------------------------------------

"""


def section(text: str, title: str) -> str:
    """The body under a '## title' heading, up to the next heading."""
    m = re.search(rf"^##\s*{re.escape(title)}\s*$(.*?)(?=^##\s|\Z)", text,
                  re.M | re.S)
    return m.group(1) if m else ""


def parse_prefs(body: str) -> dict[str, list[int]]:
    """The work preference table, as percentages per work type per stat level.

    The wiki pastes as a work name, an icon filename, then five
    'Word\\n(NN%)' cells, wrapped across lines at unpredictable places. Rather
    than model that, find each work's name and take the next five percentages
    that follow it -- which is the one thing the layout guarantees.
    """
    prefs: dict[str, list[int]] = {}
    for work in WORKS:
        m = re.search(rf"^{work}\b", body, re.M)
        if not m:
            continue
        found = re.findall(r"\((\d+)%\)", body[m.end():])
        if len(found) >= 5:
            prefs[work] = [int(x) for x in found[:5]]
    return prefs


def parse(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    risk = COUNTER_NONE
    for name in RISKS:
        if re.search(rf"\b{name}\b", section(text, "Basic Information"), re.I):
            risk = RISKS.index(name)
            break

    speed = re.search(r"E-Box Speed is ([\d.]+) boxes per second", text, re.I)
    cooldown = re.search(r"Work Cooldown is ([\d.]+)s", text, re.I)
    max_box = re.search(r"Max\s+\S*PE-Boxes\s*\n\s*(\d+)", text, re.I)

    good = re.search(r"Good\s*\n\s*(\d+)-(\d+)", text, re.I)
    normal = re.search(r"Normal\s*\n\s*(\d+)-(\d+)", text, re.I)

    escape = section(text, "Abnormality Escape Information")
    counter = re.search(r"Qliphoth counter\s+(\d+)", escape or text, re.I)
    no_counter = re.search(r"Qliphoth counter\s+X\b", escape or text, re.I)

    return {
        "id": path.stem,
        "name": lines[0] if lines else path.stem,
        "risk": risk,
        "counter": (
            COUNTER_NONE if no_counter else int(counter.group(1)) if counter else COUNTER_NONE
        ),
        "counter_stated": bool(counter or no_counter),
        "speed": float(speed.group(1)) if speed else DEFAULT_BOX_SPEED,
        "cooldown": float(cooldown.group(1)) if cooldown else DEFAULT_COOLDOWN,
        "max_box": int(max_box.group(1)) if max_box else DEFAULT_MAX_BOX,
        "good_min": int(good.group(1)) if good else 0,
        "normal_min": int(normal.group(1)) if normal else 0,
        "prefs": parse_prefs(section(text, "Abnormality Work Preferences")),
    }


def unit_attributes() -> dict[str, set[str]]:
    """Risk attributes actually set on each unit type, for the cross-check."""
    if not UNIT_DATA.is_file():
        return {}
    found: dict[str, set[str]] = {}
    wanted = set(RISK_ATTRIBUTE.values())
    for unit in ET.parse(UNIT_DATA).getroot().iter("CUnit"):
        uid = unit.get("id", "")
        on = {
            a.get("index")
            for a in unit.iter("Attributes")
            if a.get("index") in wanted and a.get("value") != "0"
        }
        found[uid] = on
    return found


def check(entries: list[dict]) -> list[str]:
    """Everything worth saying out loud at build time.

    A doc and its unit are authored on two different machines, so the one thing
    that cannot be checked by either side alone is whether they agree. The risk
    grade is written in both places and has to match: the doc's copy drives the
    admission rules, the attribute drives damage bonuses and the unit panel, and
    a disagreement between them is silent in both directions.
    """
    attrs = unit_attributes()
    notes = []
    for e in entries:
        uid = e["id"]
        if uid not in attrs:
            notes.append(f"{uid}: no CUnit with this id (the filename is the unit id)")
            continue
        want = RISK_ATTRIBUTE.get(RISKS[e["risk"]]) if e["risk"] >= 0 else None
        have = attrs[uid]
        if want is None:
            notes.append(f"{uid}: no risk grade in the doc's Basic Information")
        elif have != {want}:
            notes.append(
                f"{uid}: doc says {RISKS[e['risk']]} ({want}), unit carries "
                + (", ".join(sorted(have)) if have else "no risk attribute")
            )
        if not e["prefs"]:
            notes.append(f"{uid}: no work preference table, falling back to 50% flat")
        if not e["counter_stated"]:
            notes.append(f"{uid}: no Qliphoth counter stated, treated as X")
    return notes


def build(entries: list[dict]) -> str:
    n = max(len(entries), 1)
    out = [HEADER]
    fills: list[str] = []

    out.append(f"const int c_abnoCount = {len(entries)};\n")
    out.append(f"string[{n}] gvg_abnoType;\n")
    out.append(f"string[{n}] gvg_abnoName;\n")
    out.append(f"int[{n}] gvg_abnoRisk;\n")
    out.append("// -1 means the abnormality has no counter at all, which is not\n"
               "// the same as a counter that has run out.\n")
    out.append(f"int[{n}] gvg_abnoCounter;\n")
    out.append(f"int[{n}] gvg_abnoMaxBox;\n")
    out.append(f"fixed[{n}] gvg_abnoBoxSpeed;\n")
    out.append(f"fixed[{n}] gvg_abnoCooldown;\n")
    out.append("// Lowest box count that still reads as this result.\n")
    out.append(f"int[{n}] gvg_abnoGoodMin;\n")
    out.append(f"int[{n}] gvg_abnoNormalMin;\n")
    out.append("// Success chance per box, flattened: abnormality * 20 + work * 5 + (level-1).\n")
    out.append(f"int[{max(len(entries) * 20, 1)}] gvg_abnoPref;\n\n")

    for i, e in enumerate(entries):
        fills.append(f'    gvg_abnoType[{i}] = "{e["id"]}";')
        fills.append(f'    gvg_abnoName[{i}] = "{e["name"]}";')
        fills.append(f"    gvg_abnoRisk[{i}] = {e['risk']};")
        fills.append(f"    gvg_abnoCounter[{i}] = {e['counter']};")
        fills.append(f"    gvg_abnoMaxBox[{i}] = {e['max_box']};")
        fills.append(f"    gvg_abnoBoxSpeed[{i}] = {e['speed']};")
        fills.append(f"    gvg_abnoCooldown[{i}] = {e['cooldown']};")
        fills.append(f"    gvg_abnoGoodMin[{i}] = {e['good_min']};")
        fills.append(f"    gvg_abnoNormalMin[{i}] = {e['normal_min']};")
        for w, work in enumerate(WORKS):
            row = e["prefs"].get(work, [50] * 5)
            for lvl, pct in enumerate(row):
                fills.append(f"    gvg_abnoPref[{i * 20 + w * 5 + lvl}] = {pct};")

    out.append("void AbnoGen_Init () {\n")
    out.append("\n".join(fills) + ("\n" if fills else ""))
    out.append("}\n\n")

    out.append(
        "//--------------------------------------------------------------------------------------------------\n"
        "// The table index of a unit type, or -1. This is also what makes a unit an\n"
        "// abnormality: having a row here, which means having a doc.\n"
        "//--------------------------------------------------------------------------------------------------\n"
        "int AbnoGen_IndexOfType (string unitType) {\n"
        "    int i;\n\n"
        "    i = 0;\n"
        "    while (i < c_abnoCount) {\n"
        "        if (gvg_abnoType[i] == unitType) {\n"
        "            return i;\n"
        "        }\n"
        "        i = i + 1;\n"
        "    }\n"
        "    return -1;\n"
        "}\n\n"
        "int AbnoGen_IndexOf (unit which) {\n"
        "    if (which == null) {\n"
        "        return -1;\n"
        "    }\n"
        "    return AbnoGen_IndexOfType(UnitGetType(which));\n"
        "}\n\n"
        "bool AbnoGen_Is (unit which) {\n"
        "    return AbnoGen_IndexOf(which) >= 0;\n"
        "}\n\n"
        "//--------------------------------------------------------------------------------------------------\n"
        "// Every abnormality alive on the map, whoever owns it.\n"
        "//--------------------------------------------------------------------------------------------------\n"
        "unitgroup AbnoGen_Scan () {\n"
        "    unitgroup found;\n"
        "    int i;\n\n"
        "    found = UnitGroupEmpty();\n"
        "    i = 0;\n"
        "    while (i < c_abnoCount) {\n"
        "        UnitGroupAddUnitGroup(found, UnitGroup(gvg_abnoType[i], c_playerAny,\n"
        "                                               RegionEntireMap(), null, 0));\n"
        "        i = i + 1;\n"
        "    }\n"
        "    return found;\n"
        "}\n\n"
        "//--------------------------------------------------------------------------------------------------\n"
        "// Success chance for one work type against one stat level (1..5). Level VI\n"
        "// (EX) reads as V, because the source tables stop at V.\n"
        "//--------------------------------------------------------------------------------------------------\n"
        "int AbnoGen_Pref (int index, int work, int statLevel) {\n"
        "    if (index < 0 || index >= c_abnoCount || work < 0 || work >= 4) {\n"
        "        return 0;\n"
        "    }\n"
        "    if (statLevel < 1) {\n"
        "        statLevel = 1;\n"
        "    }\n"
        "    if (statLevel > 5) {\n"
        "        statLevel = 5;\n"
        "    }\n"
        "    return gvg_abnoPref[index * 20 + work * 5 + statLevel - 1];\n"
        "}\n"
    )
    return "".join(out)


def generate():
    entries = sorted(
        (parse(p) for p in DOCS.glob("*.md")), key=lambda e: e["id"]
    ) if DOCS.is_dir() else []
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(entries), encoding="utf-8")
    return OUT, entries, check(entries)


if __name__ == "__main__":
    path, entries, notes = generate()
    print(f"generated {path.relative_to(ROOT)}")
    for e in entries:
        grade = RISKS[e["risk"]] if e["risk"] >= 0 else "?"
        counter = "X" if e["counter"] < 0 else str(e["counter"])
        print(
            f"  {e['id']:<10} {grade:<6} qliphoth={counter:<3} "
            f"box={e['speed']}/s x{e['max_box']} good>={e['good_min']} "
            f"prefs={'yes' if e['prefs'] else 'MISSING'}  {e['name']}"
        )
    for note in notes:
        print(f"  ! {note}")
