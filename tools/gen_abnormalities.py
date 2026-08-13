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

# What a missed box costs, and to what. This encoding is emitted into the
# generated file as c_dmg* so that the mapping lives in exactly one place -- the
# script that reads the docs owns it, and everything downstream reads the
# constants rather than the numbers.
#
#   Red    the body                White  the mind
#   Black  both, in full           Pale   a percentage of maximum life
#
# The wiki writes the type twice, once as an icon filename and once as a word,
# and different pages prefer different colour words for the same two types --
# Black is sometimes purple and Pale is sometimes blue. All four spellings are
# accepted because arguing with a wiki paste is not a thing worth doing.
DAMAGE_TYPES = ["Red", "White", "Black", "Pale"]
DAMAGE_ALIASES = {"purple": "Black", "blue": "Pale"}

# O-03-03's own line. Its Details say the surrounding numbers are the default
# for every abnormality, and nothing yet contradicts that for damage.
DEFAULT_DAMAGE = ("White", 1, 2)

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


DAMAGE_WORDS = "|".join(DAMAGE_TYPES + list(DAMAGE_ALIASES))

# The wiki's line is "WhiteDamageTypeIcon.png White 1-2", tab-joined to whatever
# cell follows it. Either half alone is enough -- the icon name carries the type
# and so does the word -- so they are two patterns tried in order rather than
# one pattern with two optional halves, which would match neither.
DAMAGE_RES = [
    re.compile(rf"({DAMAGE_WORDS})DamageTypeIcon\.png[^\d\n]*(\d+)\s*-\s*(\d+)", re.I),
    re.compile(rf"\b({DAMAGE_WORDS})\b[^\d\n]*(\d+)\s*-\s*(\d+)", re.I),
]


def parse_damage(text: str) -> tuple[str, int, int] | None:
    """What a missed box costs the employee, and to what.

    Scoped to the Basic Info section first, because that is where the source
    puts it and because a colour word loose in prose is not a damage figure.
    Falls back to the whole document for a doc that never grew the section but
    states the line anyway.
    """
    canon = {t.lower(): t for t in DAMAGE_TYPES}
    canon.update({a.lower(): t for a, t in DAMAGE_ALIASES.items()})

    for body in (section(text, "Abnormality Basic Info"), text):
        if not body:
            continue
        for pattern in DAMAGE_RES:
            m = pattern.search(body)
            if not m:
                continue
            kind = canon.get(m.group(1).lower())
            if kind is None:
                continue
            lo, hi = int(m.group(2)), int(m.group(3))
            return kind, min(lo, hi), max(lo, hi)
    return None


def parse_observation(body: str) -> tuple[list[int], list[int]]:
    """Cumulative work-speed and work-success bonuses by observation level.

    The section reads as four blocks, one per level, each naming its bonus with
    an icon filename in front of it. The icon is what disambiguates: the wiki
    writes the speed bonus as "+5" and the success bonus as "+5%", but
    mechanism.md is explicit that work success is counted in points at five
    points to the percent, so the "%" is the wiki being loose and the number is
    points either way. Keying off WorkSpeedIcon / WorkSuccessIcon rather than
    off the punctuation avoids having to decide that per line.

    Index 0 is unobserved, so both arrays are five long and start at zero.
    """
    speed = [0, 0, 0, 0, 0]
    success = [0, 0, 0, 0, 0]
    level = 0
    for line in body.splitlines():
        m = re.match(r"^\s*(I|II|III|IV)\s*$", line.strip())
        if m:
            level = {"I": 1, "II": 2, "III": 3, "IV": 4}[m.group(1)]
            continue
        if level == 0:
            continue
        for icon, table in (("WorkSpeedIcon", speed), ("WorkSuccessIcon", success)):
            hit = re.search(rf"{icon}\.png[^+\-]*([+-]\s*\d+)", line)
            if hit:
                table[level] += int(hit.group(1).replace(" ", ""))
    # Levels are cumulative: reaching III means you also have I and II.
    for table in (speed, success):
        for i in range(1, 5):
            table[i] += table[i - 1]
    return speed, success


# The four purchasable sections, in the order they unlock. Observation level is
# simply how many of them a player has bought: the wiki's "(1 Section Unlocked)"
# through "(All Details Unlocked)" is a count, not four different achievements.
SECTIONS = [
    ("Abnormality Basic Info", 1),
    ("Abnormality Work Preferences", 4),   # one entry per work
    ("Abnormality Management Tips", 0),    # counted from the numbered lines
    ("Abnormality Escape Information", 1),
]


def parse_costs(text: str) -> list[int]:
    """PE-Box cost of each section.

    Every section states its own price in a "(Cost: N PE Boxes)" line, and says
    "each" when that price is per entry rather than for the block. So the block
    price is N times the number of entries, and the number of entries is either
    fixed (four works, one basic info) or counted off the numbered lines.

    Parsed rather than assumed because the prices are not uniform and are the
    thing that decides how many works it takes to know an abnormality -- which
    is the pace of the whole encyclopedia.
    """
    costs = []
    for title, entries in SECTIONS:
        body = section(text, title)
        m = re.search(r"\(Cost:?\s*(?:\S*?\s*)?(\d+)", body)
        if not m:
            costs.append(0)
            continue
        each = re.search(r"\beach\b", body, re.I) is not None
        count = entries
        if count == 0:
            count = len(re.findall(r"^\s*\d+\s", body, re.M)) or 1
        costs.append(int(m.group(1)) * (count if each else 1))
    return costs


# Where each section's lore comes from. The button on the panel shows this once
# the section is bought, so the doc's prose is the reward for buying it -- which
# is the arrangement the source has too.
LORE_SOURCE = ["Ability", "Abnormality Work Preferences",
               "Abnormality Management Tips", "Abnormality Escape Information"]


def prefs_lore(prefs: dict[str, list[int]]) -> str:
    """The preference table rendered from the parsed numbers.

    Not from the prose. The wiki paste is a tab-separated grid wrapped at
    arbitrary points, and re-flowing it produces something worse than the table
    it came from -- while the numbers behind it are already parsed and are the
    thing a player actually wants to read off this button.
    """
    if not prefs:
        return "No preference data."
    rows = ["Success per box, by the matching stat's level:"]
    rows.append("        I   II  III IV  V")
    for work in WORKS:
        row = prefs.get(work)
        if not row:
            continue
        rows.append(f"{work:<11}" + " ".join(f"{p:<3}" for p in row))
    return "<n/>".join(rows)


def parse_lore(text: str) -> list[str]:
    """One block of prose per section, flattened to a single Galaxy string.

    Wiki paste is ragged, so lines are joined with an explicit newline token
    rather than trusting the original wrapping, and the icon filenames the wiki
    leaves inline are stripped -- they are not text, they are the wiki's way of
    drawing a symbol.
    """
    out = []
    for title in LORE_SOURCE:
        body = section(text, title)
        lines = []
        for line in body.splitlines():
            line = re.sub(r"\S*Icon\.png|Risk \w+\.png|\w+Result\.png", "", line).strip()
            line = re.sub(r"^\(Cost:.*\)$", "", line).strip()
            if line:
                lines.append(line)
        # SC2 parses < > in displayed text as markup, and the wiki leaves
        # placeholders like <name> in its prose. A bare <name> reads as a tag,
        # and an unknown or empty tag is the "font style []" error. Escaped
        # before the newline separator goes in, so ours survives and theirs
        # does not.
        joined = "<n/>".join(l.replace("<", "&lt;").replace(">", "&gt;") for l in lines)
        joined = joined.replace("\t", " ").replace("\\", "").replace('"', "'")
        out.append(joined[:900])
    return out


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

    damage = parse_damage(text)

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
        "damage": damage or DEFAULT_DAMAGE,
        "damage_stated": damage is not None,
        "prefs": parse_prefs(section(text, "Abnormality Work Preferences")),
        "obs": parse_observation(section(text, "Observation Level")),
        "costs": parse_costs(text),
        "lore": parse_lore(text),
    }


def finish(entry: dict) -> dict:
    entry["lore"][1] = prefs_lore(entry["prefs"])
    return entry


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
        if not e["damage_stated"]:
            kind, lo, hi = DEFAULT_DAMAGE
            notes.append(
                f"{uid}: no Work Damage line, defaulting to {kind} {lo}-{hi}"
            )
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
    out.append(
        "// What a missed box costs, and to what. The type is per abnormality:\n"
        "// a bad work on one thing breaks the person doing it and on another\n"
        "// kills them, and which of those it is has to be readable off the\n"
        "// abnormality rather than assumed.\n"
        "//\n"
        "//   Red    the body            White  the mind\n"
        "//   Black  both, in full       Pale   a percentage of maximum life\n"
        "//\n"
        "// Pale's numbers are percentages; the other three are flat amounts.\n"
    )
    for i, name in enumerate(DAMAGE_TYPES):
        out.append(f"const int c_dmg{name} = {i};\n")
    out.append(f"int[{n}] gvg_abnoDmgType;\n")
    out.append(f"int[{n}] gvg_abnoDmgMin;\n")
    out.append(f"int[{n}] gvg_abnoDmgMax;\n")
    out.append("// Success chance per box, flattened: abnormality * 20 + work * 5 + (level-1).\n")
    out.append(f"int[{max(len(entries) * 20, 1)}] gvg_abnoPref;\n")
    out.append("// Cumulative observation bonuses, flattened: abnormality * 5 + observation\n"
               "// level. Work speed is a percentage of the base; work success is in points,\n"
               "// five to the percent.\n")
    out.append(f"int[{max(len(entries) * 5, 1)}] gvg_abnoObsSpeed;\n")
    out.append(f"int[{max(len(entries) * 5, 1)}] gvg_abnoObsSuccess;\n")
    out.append("// PE-Box price of each of the four sections, flattened:\n"
               "// abnormality * 4 + section. Observation level is how many are bought.\n")
    out.append(f"int[{max(len(entries) * 4, 1)}] gvg_abnoObsCost;\n")
    out.append("// What a bought section says, flattened abnormality * 4 + section.\n"
               "// Pushed onto the panel's buttons with UnitSetInfoButtonTooltip, which\n"
               "// is per unit INSTANCE -- so four generic abilities serve every\n"
               "// abnormality and nothing has to be generated into the catalogs.\n")
    out.append(f"string[{max(len(entries) * 4, 1)}] gvg_abnoLore;\n\n")

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
        kind, lo, hi = e["damage"]
        fills.append(f"    gvg_abnoDmgType[{i}] = c_dmg{kind};")
        fills.append(f"    gvg_abnoDmgMin[{i}] = {lo};")
        fills.append(f"    gvg_abnoDmgMax[{i}] = {hi};")
        obs_speed, obs_success = e["obs"]
        for lvl in range(5):
            fills.append(f"    gvg_abnoObsSpeed[{i * 5 + lvl}] = {obs_speed[lvl]};")
            fills.append(f"    gvg_abnoObsSuccess[{i * 5 + lvl}] = {obs_success[lvl]};")
        for sec in range(4):
            fills.append(f"    gvg_abnoObsCost[{i * 4 + sec}] = {e['costs'][sec]};")
            fills.append(f'    gvg_abnoLore[{i * 4 + sec}] = "{e["lore"][sec]}";')
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
        "}\n\n"
        "//--------------------------------------------------------------------------------------------------\n"
        "// Cumulative observation bonuses at an observation level (0 = unobserved).\n"
        "//--------------------------------------------------------------------------------------------------\n"
        "int AbnoGen_ObsSpeed (int index, int obs) {\n"
        "    if (index < 0 || index >= c_abnoCount) {\n"
        "        return 0;\n"
        "    }\n"
        "    if (obs < 0) {\n"
        "        obs = 0;\n"
        "    }\n"
        "    if (obs > 4) {\n"
        "        obs = 4;\n"
        "    }\n"
        "    return gvg_abnoObsSpeed[index * 5 + obs];\n"
        "}\n\n"
        "int AbnoGen_ObsSuccess (int index, int obs) {\n"
        "    if (index < 0 || index >= c_abnoCount) {\n"
        "        return 0;\n"
        "    }\n"
        "    if (obs < 0) {\n"
        "        obs = 0;\n"
        "    }\n"
        "    if (obs > 4) {\n"
        "        obs = 4;\n"
        "    }\n"
        "    return gvg_abnoObsSuccess[index * 5 + obs];\n"
        "}\n\n"
        "//--------------------------------------------------------------------------------------------------\n"
        "// What the next observation section costs, in that abnormality's own\n"
        "// PE-Boxes. Zero once everything is bought.\n"
        "//--------------------------------------------------------------------------------------------------\n"
        "int AbnoGen_ObsCost (int index, int obs) {\n"
        "    if (index < 0 || index >= c_abnoCount || obs < 0 || obs >= 4) {\n"
        "        return 0;\n"
        "    }\n"
        "    return gvg_abnoObsCost[index * 4 + obs];\n"
        "}\n\n"
        "//--------------------------------------------------------------------------------------------------\n"
        "// What section `sec` of this abnormality says.\n"
        "//--------------------------------------------------------------------------------------------------\n"
        "string AbnoGen_Lore (int index, int sec) {\n"
        "    if (index < 0 || index >= c_abnoCount || sec < 0 || sec >= 4) {\n"
        "        return \"\";\n"
        "    }\n"
        "    return gvg_abnoLore[index * 4 + sec];\n"
        "}\n\n"
        "//--------------------------------------------------------------------------------------------------\n"
        "// What a missed box on this abnormality costs. Defaults to White so that\n"
        "// an unknown index costs the mind rather than the body -- the cheaper way\n"
        "// to be wrong.\n"
        "//--------------------------------------------------------------------------------------------------\n"
        "int AbnoGen_DmgType (int index) {\n"
        "    if (index < 0 || index >= c_abnoCount) {\n"
        "        return c_dmgWhite;\n"
        "    }\n"
        "    return gvg_abnoDmgType[index];\n"
        "}\n\n"
        "int AbnoGen_DmgRoll (int index) {\n"
        "    if (index < 0 || index >= c_abnoCount) {\n"
        "        return 0;\n"
        "    }\n"
        "    return RandomInt(gvg_abnoDmgMin[index], gvg_abnoDmgMax[index]);\n"
        "}\n\n"
        "string AbnoGen_DmgName (int type) {\n"
    )
    for name in DAMAGE_TYPES:
        out.append(f'    if (type == c_dmg{name}) {{ return "{name}"; }}\n')
    out.append(
        '    return "?";\n'
        "}\n\n"
        "//--------------------------------------------------------------------------------------------------\n"
        "// The damage line as a player would read it, for tooltips and debug.\n"
        "//--------------------------------------------------------------------------------------------------\n"
        "string AbnoGen_DmgText (int index) {\n"
        "    if (index < 0 || index >= c_abnoCount) {\n"
        "        return \"\";\n"
        "    }\n"
        "    return AbnoGen_DmgName(gvg_abnoDmgType[index]) + \" \"\n"
        "           + IntToString(gvg_abnoDmgMin[index]) + \"-\"\n"
        "           + IntToString(gvg_abnoDmgMax[index]);\n"
        "}\n"
    )
    return "".join(out)


def generate():
    entries = sorted(
        (finish(parse(p)) for p in DOCS.glob("*.md")), key=lambda e: e["id"]
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
            f"dmg={e['damage'][0]} {e['damage'][1]}-{e['damage'][2]} "
            f"obs=+{e['obs'][0][4]}spd/+{e['obs'][1][4]}suc "
            f"cost={'/'.join(str(c) for c in e['costs'])} "
            f"prefs={'yes' if e['prefs'] else 'MISSING'}  {e['name']}"
        )
    for note in notes:
        print(f"  ! {note}")
