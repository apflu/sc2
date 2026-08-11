#!/usr/bin/env python3
"""Generate Galaxy lookup tables from the map's editor-authored content.

Two things get extracted:

  Unit types, from Base.SC2Data/GameData/UnitData.xml. Custom units follow the
  naming convention Lob_<Category>_<Variant>, so the category falls out of the
  id and a new variant needs no code change -- it lands in its category's type
  table automatically, including for runtime spawning.

  Editor regions, from Regions. Same story as groups: the file is plain XML
  carrying both the name typed in the editor and the id the engine knows the
  region by, so the ids get read here instead of transcribed. Regions are how
  a room reaches the script -- a rest hall is a shape with walls, and no
  arrangement of circles around a unit is that shape.

  Object groups, from Objects. The editor assigns placed objects random ids
  that cannot be chosen by hand, so binding to them by convention is out; but
  the file is plain XML, so the ids can just be read here instead of being
  copied around by hand. Groups are how a named subset of placed objects
  (a sector, a starting cluster) reaches the script.

Output is src/galaxy/05_objects_gen.galaxy, committed like MapScript.galaxy.
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "LobotomyShiphold.SC2Map"
UNIT_DATA = MAP / "Base.SC2Data" / "GameData" / "UnitData.xml"
OBJECTS = MAP / "Objects"
REGIONS = MAP / "Regions"
OUT = ROOT / "src" / "galaxy" / "05_objects_gen.galaxy"

PREFIX = "Lob_"
INT32_MAX = 2**31 - 1

# Categories the Galaxy side expects to exist. Emitted with empty tables when no
# unit has been authored yet, so code referencing ObjectsGen_ScanDevice() still
# compiles and simply finds nothing -- the two machines don't have to land their
# halves in the same order. A scan of an empty table returns an empty group and
# the predicate returns false, so unwritten content stays inert rather than
# breaking the build.
EXPECTED_CATEGORIES = [
    "Core",
    "CoreDown",
    "Debris",
    "Device",
    "DeviceDown",
    "Hero",
    "Marker",
    "Pile",
    "Recycler",
    "SCV",
    "SCV_Miner",
    "SCV_Worker",
]

HEADER = """//--------------------------------------------------------------------------------------------------
// GENERATED FILE -- DO NOT EDIT.
//
// Built from the map's UnitData.xml and Objects by tools/gen_objects.py.
// Place things in the editor, rebuild, and the tables below follow.
//--------------------------------------------------------------------------------------------------

"""


def read_categories() -> dict[str, list[str]]:
    """Bucket custom unit types under every prefix of their id.

    Lob_SCV_Miner registers under both SCV and SCV_Miner, so the script can ask
    at whichever level it means -- every SCV, or specifically the miners -- and
    a new variant slots under its existing prefixes without a code change.
    """
    if not UNIT_DATA.is_file():
        return {c: [] for c in EXPECTED_CATEGORIES}

    categories: dict[str, list[str]] = {c: [] for c in EXPECTED_CATEGORIES}
    for unit in ET.parse(UNIT_DATA).getroot().iter("CUnit"):
        uid = unit.get("id", "")
        if not uid.startswith(PREFIX):
            continue
        parts = [re.sub(r"\W", "", p) for p in uid.split("_")[1:] if p]
        for depth in range(1, len(parts) + 1):
            categories.setdefault("_".join(parts[:depth]), []).append(uid)

    return {k: sorted(v) for k, v in sorted(categories.items())}


def read_groups() -> list[tuple[str, list[int]]]:
    """Editor object groups, as (name, [placed object ids])."""
    if not OBJECTS.is_file():
        return []

    groups = []
    for group in ET.parse(OBJECTS).getroot().iter("Group"):
        # The editor stores whatever was typed into the name field, trailing
        # newline included. Left unstripped it silently breaks name matching.
        name = (group.get("Name") or "").strip()
        if not name:
            continue
        ids = [int(m.get("Id")) for m in group.iter("GroupObject") if m.get("Id")]
        for oid in ids:
            if oid > INT32_MAX:
                raise SystemExit(
                    f"object id {oid} in group '{name}' exceeds Galaxy's signed "
                    f"32-bit int; the id table would silently wrap"
                )
        groups.append((name, ids))

    return sorted(groups)


def read_regions() -> list[tuple[str, int]]:
    """Editor regions, as (name, id).

    The file only exists once at least one region has been drawn, so its
    absence is normal rather than an error: the tables come out empty and the
    lookups return an empty region, which leaves anything built on regions
    inert instead of broken.
    """
    if not REGIONS.is_file():
        return []

    regions = []
    for region in ET.parse(REGIONS).getroot().iter("region"):
        rid = region.get("id")
        name_el = region.find("name")
        if rid is None or name_el is None:
            continue
        # Same trailing-whitespace trap as group names.
        name = (name_el.get("value") or "").strip()
        if name:
            regions.append((name, int(rid)))

    return sorted(regions)


def emit_string_array(name: str, values: list[str]) -> str:
    """Galaxy wants a literal array length and has no initialisers, so the
    length is emitted inline and the fill happens in the init function."""
    return f"const int c_{name}Count = {len(values)};\nstring[{max(len(values), 1)}] gvg_{name};\n"


def build() -> str:
    categories = read_categories()
    groups = read_groups()
    regions = read_regions()

    out = [HEADER]
    fills: list[str] = []

    out.append("// Unit types, by the category segment of their id.\n")
    for category, types in categories.items():
        out.append(emit_string_array(f"types{category}", types))
        fills.extend(f'    gvg_types{category}[{i}] = "{t}";' for i, t in enumerate(types))
    out.append("\n")

    members = [oid for _, ids in groups for oid in ids]
    out.append("// Editor object groups, flattened: names[i] owns the members\n")
    out.append("// slice starting at groupFirst[i] and running groupSize[i] long.\n")
    out.append(f"const int c_groupCount = {len(groups)};\n")
    out.append(f"string[{max(len(groups), 1)}] gvg_groupNames;\n")
    out.append(f"int[{max(len(groups), 1)}] gvg_groupFirst;\n")
    out.append(f"int[{max(len(groups), 1)}] gvg_groupSize;\n")
    out.append(f"int[{max(len(members), 1)}] gvg_groupMembers;\n\n")

    cursor = 0
    for i, (name, ids) in enumerate(groups):
        fills.append(f'    gvg_groupNames[{i}] = "{name}";')
        fills.append(f"    gvg_groupFirst[{i}] = {cursor};")
        fills.append(f"    gvg_groupSize[{i}] = {len(ids)};")
        cursor += len(ids)
    fills.extend(f"    gvg_groupMembers[{i}] = {oid};" for i, oid in enumerate(members))

    out.append("void ObjectsGen_Init () {\n")
    out.append("\n".join(fills) + ("\n" if fills else ""))
    out.append("}\n\n")

    # One scan per category. Galaxy has no array parameters, so a shared helper
    # taking a type table is not expressible -- emit the loop per category.
    for category, types in categories.items():
        out.append(
            f"//--------------------------------------------------------------------------------------------------\n"
            f"// Every live {category} unit on the map, whichever variant and whoever owns it.\n"
            f"// Works for runtime-spawned units too, unlike anything keyed on placed ids.\n"
            f"//--------------------------------------------------------------------------------------------------\n"
            f"unitgroup ObjectsGen_Scan{category} () {{\n"
            f"    unitgroup found;\n"
            f"    int i;\n\n"
            f"    found = UnitGroupEmpty();\n"
            f"    i = 0;\n"
            f"    while (i < c_types{category}Count) {{\n"
            f"        UnitGroupAddUnitGroup(found, UnitGroup(gvg_types{category}[i], c_playerAny,\n"
            f"                                               RegionEntireMap(), null, 0));\n"
            f"        i = i + 1;\n"
            f"    }}\n"
            f"    return found;\n"
            f"}}\n\n"
            f"//--------------------------------------------------------------------------------------------------\n"
            f"// Whether a unit is a {category}, whatever variant. False for an empty\n"
            f"// category, so code can be written ahead of the units existing.\n"
            f"//--------------------------------------------------------------------------------------------------\n"
            f"bool ObjectsGen_Is{category} (unit target) {{\n"
            f"    int i;\n\n"
            f"    if (target == null) {{\n"
            f"        return false;\n"
            f"    }}\n"
            f"    i = 0;\n"
            f"    while (i < c_types{category}Count) {{\n"
            f"        if (UnitGetType(target) == gvg_types{category}[i]) {{\n"
            f"            return true;\n"
            f"        }}\n"
            f"        i = i + 1;\n"
            f"    }}\n"
            f"    return false;\n"
            f"}}\n\n"
        )

    out.append(
        "//--------------------------------------------------------------------------------------------------\n"
        "// The placed objects of a named editor group. Preplaced only -- runtime\n"
        "// spawns have no group. Returns empty for an unknown name.\n"
        "//--------------------------------------------------------------------------------------------------\n"
        "unitgroup ObjectsGen_Group (string name) {\n"
        "    unitgroup found;\n"
        "    int i;\n"
        "    int m;\n\n"
        "    found = UnitGroupEmpty();\n"
        "    i = 0;\n"
        "    while (i < c_groupCount) {\n"
        "        if (gvg_groupNames[i] == name) {\n"
        "            m = gvg_groupFirst[i];\n"
        "            while (m < gvg_groupFirst[i] + gvg_groupSize[i]) {\n"
        "                UnitGroupAdd(found, UnitFromId(gvg_groupMembers[m]));\n"
        "                m = m + 1;\n"
        "            }\n"
        "            return found;\n"
        "        }\n"
        "        i = i + 1;\n"
        "    }\n"
        "    return found;\n"
        "}\n"
    )

    out.append(
        "\n// Editor regions, by the name typed in the editor.\n"
        f"const int c_regionCount = {len(regions)};\n"
        f"string[{max(len(regions), 1)}] gvg_regionNames;\n"
        f"int[{max(len(regions), 1)}] gvg_regionIds;\n"
    )
    fills.extend(
        f'    gvg_regionNames[{i}] = "{n}";\n    gvg_regionIds[{i}] = {rid};'
        for i, (n, rid) in enumerate(regions)
    )

    out.append(
        "\n//----------------------------------------------------------------"
        "----------------------------------\n"
        "// The editor region of that name, or an empty region if there is none.\n"
        "// Empty rather than null so callers can use the result unconditionally.\n"
        "//----------------------------------------------------------------"
        "----------------------------------\n"
        "region ObjectsGen_Region (string name) {\n"
        "    int i;\n"
        "\n"
        "    i = 0;\n"
        "    while (i < c_regionCount) {\n"
        "        if (gvg_regionNames[i] == name) {\n"
        "            return RegionFromId(gvg_regionIds[i]);\n"
        "        }\n"
        "        i = i + 1;\n"
        "    }\n"
        "    return RegionEmpty();\n"
        "}\n"
    )

    return "".join(out)


def generate() -> tuple[Path, dict[str, list[str]], list[tuple[str, list[int]]], list[tuple[str, int]]]:
    categories = read_categories()
    groups = read_groups()
    regions = read_regions()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    return OUT, categories, groups, regions


if __name__ == "__main__":
    path, cats, grps, regs = generate()
    print(f"generated {path.relative_to(ROOT)}")
    for name, types in cats.items():
        print(f"  {name}: {', '.join(types)}")
    for name, ids in grps:
        print(f"  group '{name}': {len(ids)} objects")
    for name, rid in regs:
        print(f"  region '{name}': id {rid}")
