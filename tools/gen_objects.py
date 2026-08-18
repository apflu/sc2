#!/usr/bin/env python3
"""Generate Galaxy lookup tables from the map's editor-authored content.

Two things get extracted:

  Unit types, from Base.SC2Data/GameData/UnitData.xml. Custom units follow the
  naming convention Lob_<Category>_<Variant>, so the category falls out of the
  id and a new variant needs no code change -- it lands in its category's type
  table automatically, including for runtime spawning.

  Department upgrades, from UpgradeData.xml. Upgrades are real CUpgrade
  entries authored in the data editor, one per level, following

      <Sephirot>_Upg<line>_<level>[_Ally]

  so Malkuth_Upg2_1 and Malkuth_Upg2_1_Ally are the owner's and the allies'
  version of the same step. Splitting the id here means the script side stays
  generic: it never names an upgrade, it only knows the shape of the name.

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
UPGRADE_DATA = MAP / "Base.SC2Data" / "GameData" / "UpgradeData.xml"
ABIL_DATA = MAP / "Base.SC2Data" / "GameData" / "AbilData.xml"
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
    "Abno",
    "Core",
    "CoreDown",
    "Debris",
    "Device",
    "DeviceDown",
    "Door",
    "DoorDown",
    "Emp",
    "Guard",
    "Hero",
    "Marker",
    "Ordeal",
    "Ordeal_Dawn",
    "Ordeal_Dusk",
    "Ordeal_Midnight",
    "Ordeal_Noon",
    "Panel",
    "Pile",
    "Recycler",
    "Salvage",
    "Turret",
    "SCV",
    "SCV_Miner",
    "SCV_Worker",
    "Tool",
]

CATALOG_FIELDS = ROOT / "tools" / "catalog_fields.txt"

HEADER = """//--------------------------------------------------------------------------------------------------
// GENERATED FILE -- DO NOT EDIT.
//
// Built from the map's UnitData.xml and Objects by tools/gen_objects.py.
// Place things in the editor, rebuild, and the tables below follow.
//--------------------------------------------------------------------------------------------------

"""


def check_catalogs() -> None:
    """Parse every catalog in GameData, not just the two that get read.

    A malformed catalog is not a build error by itself — gen_objects only opens
    UnitData and UpgradeData — so a broken BehaviorData or ActorData would sail
    through the build and fail in the editor instead, a machine and a git round
    trip away from whoever wrote it.

    The recurring offender is "--" inside an XML comment, which is illegal and
    which prose runs into constantly. Use an em dash.
    """
    data_dir = MAP / "Base.SC2Data" / "GameData"
    if not data_dir.is_dir():
        return
    roots = {}
    for path in sorted(data_dir.glob("*.xml")):
        try:
            roots[path.name] = ET.parse(path).getroot()
        except ET.ParseError as exc:
            raise SystemExit(f"{path.name}: {exc}") from exc
    check_catalog_fields(roots)
    check_weapons(roots)


def check_weapons(roots: dict) -> None:
    """Refuse a weapon with no Effect or no Range.

    Neither is a thing anybody writes and then forgets. They go missing another
    way: THE EDITOR REWRITES OUR CATALOGS WHEN IT SAVES, and if it failed to
    load one it will happily save over it with whatever it managed to keep.
    That is how both weapons on the map lost Range, Backswing and Effect at
    once, which reads in game as a player character that simply cannot attack —
    no error, no missing button, just a unit that walks up to things and stands
    there.

    Two fields rather than a full schema because these two are the ones whose
    absence is silent. A weapon with no Effect fires and does nothing; a weapon
    with range 0 never fires at all.
    """
    bad = []
    for name, root in sorted(roots.items()):
        for w in root:
            if not isinstance(w.tag, str) or not w.tag.startswith("CWeapon"):
                continue
            have = {c.tag for c in w}
            for field in ("Effect", "Range"):
                if field not in have:
                    bad.append(f"  {name}: <{w.tag} id=\"{w.get('id', '?')}\"> has no <{field}>")

    if bad:
        raise SystemExit(
            "a weapon that cannot work. Usually the editor saved over a catalog\n"
            "it had failed to load; in game this is a unit that will not attack\n"
            "and says nothing about why:\n" + "\n".join(bad))


def family(cls: str) -> str:
    """CBehaviorAttribute -> CBehavior, CAbilEffectTarget -> CAbil.

    Fields declared on a base class are usable by every class under it, and
    stock only demonstrates each one wherever it happened to be needed. InfoIcon
    is a CBehavior field and stock never puts one on a CBehaviorAttribute, so
    without this the table would call ours a mistake.
    """
    m = re.match(r"(C[A-Z][a-z]+)", cls)
    return m.group(1) if m else cls


def loose_key(cls: str, parent: str, child: str) -> str:
    """The same triple with both class names blurred to their families.

    The PARENT has to be blurred too, not just the owning class: the outermost
    parent of any field is the entry element itself, so InfoIcon on a
    CBehaviorAttribute reads as CBehavior/CBehaviorAttribute/InfoIcon while
    stock only ever shows CBehavior/CBehaviorBuff/InfoIcon. Blurring one end
    and not the other leaves every base-class field on a rarer sibling looking
    invented.
    """
    if re.match(r"C[A-Z]", parent):
        parent = family(parent)
    return f"{family(cls)}\t{parent}\t{child}"


def check_catalog_fields(roots: dict) -> None:
    """Refuse a real field name in a place the engine will not look for it.

    THE EDITOR'S ONLY COMPLAINT IS A WARNING IN A LOG, and the field is then
    silently ignored at runtime — so this fails as a unit that quietly does not
    have the thing you gave it, which is indistinguishable from the thing not
    working.

        <CBehaviorBuff id="Lob_Mind_White">
            <Modification>
                <DamageResponse .../>      <-- real field, wrong parent

    DamageResponse hangs directly off the behavior. DeathResponse, which looks
    like its twin, goes inside Modification. Nothing about either name says so
    and there is no schema shipped with the game, so the permitted set is
    harvested from Blizzard's own data: tools/catalog_fields.txt, every
    (class, parent, child) triple that appears anywhere in it.

    Matched by class family rather than exact class, and skipped entirely for a
    class stock has never used, so the list errs wide. A false positive stops a
    build that would have worked, which is worse than missing one exotic field.
    """
    if not CATALOG_FIELDS.is_file():
        return

    exact = set()
    loose = set()
    seen_classes = set()
    for line in CATALOG_FIELDS.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        cls, parent, child = parts
        exact.add(line)
        loose.add(loose_key(cls, parent, child))
        seen_classes.add(cls)

    bad = []

    def walk(cls: str, entry_id: str, el, name: str) -> None:
        for child in el:
            if not isinstance(child.tag, str):
                continue
            if (f"{cls}\t{el.tag}\t{child.tag}" not in exact
                    and loose_key(cls, el.tag, child.tag) not in loose):
                bad.append(f"  {name}: <{cls} id=\"{entry_id}\"> "
                           f"has <{child.tag}> inside <{el.tag}>")
            walk(cls, entry_id, child, name)

    for name, root in sorted(roots.items()):
        for entry in root:
            if not isinstance(entry.tag, str) or entry.tag not in seen_classes:
                continue
            walk(entry.tag, entry.get("id", "?"), entry, name)

    if bad:
        raise SystemExit(
            "catalog field in a place the engine does not look for it. The\n"
            'editor says "Unable to find field" in a log and then ignores it, so\n'
            "the unit simply does not have what you gave it:\n"
            + "\n".join(sorted(set(bad))))


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


UPGRADE_RE = re.compile(r"^([A-Za-z]+)_Upg(\d+)_(\d+)(_Ally)?$")


def read_upgrades() -> list[dict]:
    """Department upgrades, split into department / line / level / ally."""
    if not UPGRADE_DATA.is_file():
        return []

    upgrades = []
    for upgrade in ET.parse(UPGRADE_DATA).getroot().iter("CUpgrade"):
        uid = upgrade.get("id", "")
        m = UPGRADE_RE.match(uid)
        if not m:
            # Not everything in the catalog has to be a department upgrade.
            continue
        upgrades.append(
            {
                "id": uid,
                "dept": m.group(1),
                "line": f"{m.group(1)}_Upg{m.group(2)}",
                "level": int(m.group(3)),
                "ally": bool(m.group(4)),
            }
        )

    return sorted(upgrades, key=lambda u: (u["line"], u["level"], u["ally"]))


def read_builds() -> list[dict]:
    """Which ability command puts up which unit.

    A CAbilBuild's InfoArray rows are its commands in order, and the command
    index is that position counting from zero -- Build1 is 0, Build2 is 1. Not
    a guess: liberty's thanson02 issues AbilityCommand("TerranBuild", 1) at a
    point and gets a SupplyDepot, which is the Build2 row.

    Reading it here is what lets the fortification code order a real build
    instead of conjuring the finished unit. Nothing else can supply the pair
    (ability, index) -- it exists only as the shape of the catalog.
    """
    if not ABIL_DATA.is_file():
        return []

    builds = []
    for abil in ET.parse(ABIL_DATA).getroot().iter("CAbilBuild"):
        link = abil.get("id", "")
        for index, info in enumerate(abil.iter("InfoArray")):
            unit = info.get("Unit", "")
            if unit:
                builds.append({"unit": unit, "abil": link, "index": index})
    return sorted(builds, key=lambda b: b["unit"])


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


FILL_RE = re.compile(r"^\s*(gvg_\w+)\[", re.M)


def check_fills(declared: list[tuple[str, int]], text: str) -> None:
    """Refuse to emit a table that has rows but no assignments.

    Galaxy has no array initialisers, so every generated table is a declaration
    up top and a run of assignments in ObjectsGen_Init, with nothing connecting
    the two. A table whose rows never got emitted is not a compile error -- it
    is a null string handed to StringLength at runtime, which is a crash a long
    way from its cause, or worse, an empty string compared against and silently
    matching nothing.

    Driven off the row counts rather than the declared lengths, because an empty
    table is declared at length 1 anyway (Galaxy rejects a zero-length array)
    and the two cases are indistinguishable in the text.
    """
    filled = set(FILL_RE.findall(text))
    missing = sorted({name for name, rows in declared if rows > 0 and name not in filled})
    if missing:
        raise SystemExit(
            "generator bug: declared but never filled in ObjectsGen_Init: "
            + ", ".join(missing)
        )


def build() -> str:
    categories = read_categories()
    groups = read_groups()
    regions = read_regions()
    upgrades = read_upgrades()
    builds = read_builds()

    out = [HEADER]
    fills: list[str] = []
    declared: list[tuple[str, int]] = []

    out.append("// Unit types, by the category segment of their id.\n")
    for category, types in categories.items():
        out.append(emit_string_array(f"types{category}", types))
        declared.append((f"gvg_types{category}", len(types)))
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
    declared += [
        ("gvg_groupNames", len(groups)),
        ("gvg_groupFirst", len(groups)),
        ("gvg_groupSize", len(groups)),
        ("gvg_groupMembers", len(members)),
    ]

    cursor = 0
    for i, (name, ids) in enumerate(groups):
        fills.append(f'    gvg_groupNames[{i}] = "{name}";')
        fills.append(f"    gvg_groupFirst[{i}] = {cursor};")
        fills.append(f"    gvg_groupSize[{i}] = {len(ids)};")
        cursor += len(ids)
    fills.extend(f"    gvg_groupMembers[{i}] = {oid};" for i, oid in enumerate(members))

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

    builds = read_builds()
    n = max(len(builds), 1)
    out.append(
        "\n//--------------------------------------------------------------------------------------------------\n"
        "// Build commands, read out of the map's own AbilData.xml.\n"
        "//\n"
        "// A CAbilBuild's InfoArray rows ARE its commands, in order, counting from\n"
        "// zero. Nothing else can supply this pair: (ability, index) exists only as\n"
        "// the shape of the catalog, and a script that wanted to order a real build\n"
        "// would otherwise have to hardcode a number that moves whenever somebody\n"
        "// inserts a row above it.\n"
        "//\n"
        "// Empty until a CAbilBuild is authored, which is what keeps the code that\n"
        "// reads it inert rather than broken.\n"
        "//--------------------------------------------------------------------------------------------------\n"
        f"const int c_buildCount = {len(builds)};\n"
        f"string[{n}] gvg_buildUnit;\n"
        f"string[{n}] gvg_buildAbil;\n"
        f"int[{n}] gvg_buildIndex;\n"
    )
    fills.extend(
        f'    gvg_buildUnit[{i}] = "{b["unit"]}";\n'
        f'    gvg_buildAbil[{i}] = "{b["abil"]}";\n'
        f"    gvg_buildIndex[{i}] = {b['index']};"
        for i, b in enumerate(builds)
    )
    known = {u["id"] for u in upgrades}
    out.append(
        "\n// Department upgrades, split out of their ids. The ally variant is\n"
        "// resolved here so the script never has to build a name by hand.\n"
        f"const int c_deptUpgradeCount = {len(upgrades)};\n"
        f"string[{max(len(upgrades), 1)}] gvg_deptUpgradeId;\n"
        f"string[{max(len(upgrades), 1)}] gvg_deptUpgradeLine;\n"
        f"string[{max(len(upgrades), 1)}] gvg_deptUpgradeAlly;\n"
        f"int[{max(len(upgrades), 1)}] gvg_deptUpgradeLevel;\n"
        f"bool[{max(len(upgrades), 1)}] gvg_deptUpgradeIsAlly;\n"
    )
    declared += [
        ("gvg_deptUpgradeId", len(upgrades)),
        ("gvg_deptUpgradeLine", len(upgrades)),
        ("gvg_deptUpgradeAlly", len(upgrades)),
        ("gvg_deptUpgradeLevel", len(upgrades)),
        ("gvg_deptUpgradeIsAlly", len(upgrades)),
    ]
    for i, u in enumerate(upgrades):
        ally = f'{u["id"]}_Ally'
        fills.append(
            f'    gvg_deptUpgradeId[{i}] = "{u["id"]}";\n'
            f'    gvg_deptUpgradeLine[{i}] = "{u["line"]}";\n'
            f'    gvg_deptUpgradeAlly[{i}] = "{ally if ally in known else ""}";\n'
            f'    gvg_deptUpgradeLevel[{i}] = {u["level"]};\n'
            f'    gvg_deptUpgradeIsAlly[{i}] = {"true" if u["ally"] else "false"};'
        )

    out.append(
        "\n// Editor regions, by the name typed in the editor.\n"
        f"const int c_regionCount = {len(regions)};\n"
        f"string[{max(len(regions), 1)}] gvg_regionNames;\n"
        f"int[{max(len(regions), 1)}] gvg_regionIds;\n"
    )
    declared += [("gvg_regionNames", len(regions)), ("gvg_regionIds", len(regions))]
    fills.extend(
        f'    gvg_regionNames[{i}] = "{n}";\n    gvg_regionIds[{i}] = {rid};'
        for i, (n, rid) in enumerate(regions)
    )

    out.append(
        "\n//----------------------------------------------------------------"
        "----------------------------------\n"
        "// The ability command that builds this unit type, and its index.\n"
        "//\n"
        "// \"\" and -1 when the map has no build command for it, which is the\n"
        "// answer callers have to be able to act on: an emplacement nobody can\n"
        "// order built is a position that stays empty, not a crash.\n"
        "//----------------------------------------------------------------"
        "----------------------------------\n"
        "string ObjectsGen_BuildAbil (string unitType) {\n"
        "    int i;\n"
        "\n"
        "    i = 0;\n"
        "    while (i < c_buildCount) {\n"
        "        if (gvg_buildUnit[i] == unitType) {\n"
        "            return gvg_buildAbil[i];\n"
        "        }\n"
        "        i = i + 1;\n"
        "    }\n"
        "    return \"\";\n"
        "}\n"
        "\n"
        "int ObjectsGen_BuildIndex (string unitType) {\n"
        "    int i;\n"
        "\n"
        "    i = 0;\n"
        "    while (i < c_buildCount) {\n"
        "        if (gvg_buildUnit[i] == unitType) {\n"
        "            return gvg_buildIndex[i];\n"
        "        }\n"
        "        i = i + 1;\n"
        "    }\n"
        "    return -1;\n"
        "}\n"
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

    # Emitted last, after every table above has contributed its fills.
    #
    # It used to sit in the middle, right after the unit-type and group tables,
    # which meant the upgrade and region fills appended below it were collected
    # into a list nobody read again. The region table then declared a count of 1
    # over an array of nulls, and the first StringLength on it took the map
    # down; the upgrade table failed silently, which was worse.
    #
    # Position is the fix. A fill added anywhere in build() is now emitted by
    # construction, and check_fills below refuses to write a file where one is
    # not.
    out.append("void ObjectsGen_Init () {\n")
    out.append("\n".join(fills) + ("\n" if fills else ""))
    out.append("}\n")

    check_fills(declared, "".join(out))
    return "".join(out)


def generate():
    check_catalogs()
    categories = read_categories()
    groups = read_groups()
    regions = read_regions()
    upgrades = read_upgrades()
    builds = read_builds()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    return OUT, categories, groups, regions, upgrades, builds


if __name__ == "__main__":
    path, cats, grps, regs, upgs = generate()
    print(f"generated {path.relative_to(ROOT)}")
    for name, types in cats.items():
        print(f"  {name}: {', '.join(types)}")
    for name, ids in grps:
        print(f"  group '{name}': {len(ids)} objects")
    for name, rid in regs:
        print(f"  region '{name}': id {rid}")
    for u in upgs:
        print(f"  upgrade {u['id']}: line {u['line']} lv{u['level']}"
              + (" (ally)" if u["ally"] else ""))
