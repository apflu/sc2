#!/usr/bin/env python3
"""Concatenate src/galaxy/*.galaxy into the map's MapScript.galaxy.

Source of truth is src/galaxy/. The generated MapScript.galaxy is committed so
the map runs without a build step on the Windows side, but it must never be
edited by hand -- rerun this script instead.

Modules are concatenated in filename order, so numeric prefixes control
declaration order (Galaxy requires a function to be defined before it is used).

Any module that declares a function matching `void <Name>_Init ()` gets that
function called from InitMap(), in module order.
"""

import re
import sys
from pathlib import Path

import gen_abnormalities
import gen_objects
import gen_strings

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "galaxy"
OUT = ROOT / "LobotomyShiphold.SC2Map" / "MapScript.galaxy"

INIT_RE = re.compile(r"^void\s+(\w+_Init)\s*\(\s*\)", re.MULTILINE)

BANNER = """//==================================================================================================
//
// GENERATED FILE -- DO NOT EDIT.
//
// Built from src/galaxy/ by tools/build_galaxy.py
// Edit the sources there and rerun the build.
//
//==================================================================================================
include "TriggerLibs/NativeLib"

"""


DEF_RE = re.compile(
    r"^(?:void|bool|int|fixed|string|unit|unitgroup|point|region|text|order|timer|trigger|"
    r"playergroup|abilcmd|actor|bank|color|doodad|sound|wave)\s+(\w+)\s*\(", re.M)
CALL_RE = re.compile(r"\b(\w+)\s*\(")


def check_forward_refs(text: str) -> None:
    """Refuse to emit a script that calls one of our functions before defining it.

    Galaxy needs a declaration before its use and the modules are concatenated in
    filename order, so a call sitting above its own definition is a compile
    error -- and the compiler reports it as "invalid argument list" AT THE CALL
    SITE, which reads like a signature problem and sends you looking in the wrong
    place entirely. It has cost four debugging rounds, every one of them a block
    that moved or a call that crossed a module boundary.

    Only our own functions are checked. A native or library call is declared long
    before any of this and is indistinguishable here from a call to something
    that does not exist at all -- which is a different mistake, and one the
    compiler names clearly.
    """
    stripped = re.sub(r"//[^\n]*", "", text)

    # Where each function's name appears in its own definition. Both passes run
    # over the same stripped text so the offsets are comparable, and the
    # definition's own name would otherwise look like the first call to it.
    defined_at = {}
    heads = set()
    for m in DEF_RE.finditer(stripped):
        heads.add(m.start(1))
        defined_at.setdefault(m.group(1), m.start(1))

    bad = []
    for m in CALL_RE.finditer(stripped):
        at = defined_at.get(m.group(1))
        if at is not None and m.start(1) < at and m.start(1) not in heads:
            bad.append((text.count("\n", 0, m.start(1)) + 1, m.group(1)))

    seen = set()
    unique = [b for b in bad if not (b[1] in seen or seen.add(b[1]))]
    if unique:
        raise SystemExit(
            "forward reference: called before it is defined, which Galaxy reports\n"
            'as "invalid argument list" at the call site:\n'
            + "\n".join(f"  MapScript.galaxy line {line}: {name}" for line, name in unique)
        )


# Every type name the Galaxy compiler knows, harvested once from the native
# declarations in core.sc2mod. The handle types are the dangerous half: `int`
# and `bool` are obviously keywords and nobody names a variable `int`, but
# `marker`, `order`, `wave`, `text`, `color`, `bank`, `sound` and `point` all
# read as perfectly ordinary English nouns.
TYPE_NAMES = {
    "abilcmd", "actor", "actorscope", "aifilter", "bank", "bitmask", "bool", "byte",
    "camerainfo", "color", "datetime", "doodad", "effecthistory", "fixed",
    "generichandle", "int", "marker", "order", "playergroup", "point", "region",
    "revealer", "sound", "soundlink", "string", "text", "timer",
    "transmissionsource", "trigger", "unit", "unitfilter", "unitgroup", "unitref",
    "wave", "waveinfo", "wavetarget",
}

DECL_RE = re.compile(
    r"\b(" + "|".join(sorted(TYPE_NAMES)) + r")\s*(?:\[\s*\d+\s*\])?\s+(\w+)")


def check_type_names(text: str) -> None:
    """Refuse to name a variable, parameter or field after a Galaxy type.

    `unit marker` is not a unit called marker; it is two type keywords in a row,
    and the compiler says "invalid list of args" -- pointing at the FUNCTION
    HEADER, which reads exactly like a forward reference and is not one. That
    cost a full round trip to the Windows machine to find.

    The handle types are what makes this worth a check. Nobody writes `int int`,
    but `marker`, `order`, `wave`, `text`, `color`, `bank`, `point` and `sound`
    are ordinary words that describe the thing being stored, so the name that
    first comes to mind is exactly the one that will not compile.
    """
    bad = []
    for i, line in enumerate(text.splitlines(), 1):
        s = re.sub(r"//.*", "", line)
        s = re.sub(r'"(\\.|[^"\\])*"', '""', s)
        for m in DECL_RE.finditer(s):
            if m.group(2) in TYPE_NAMES:
                bad.append((i, m.group(2), line.strip()))

    if bad:
        raise SystemExit(
            "type name used as an identifier -- Galaxy reports this as\n"
            '"invalid list of args", pointing at the function header:\n'
            + "\n".join(f"  MapScript.galaxy line {n}: {word!r} in {src}"
                        for n, word, src in bad)
        )


GLOBAL_DECL_RE = re.compile(
    r"^(?:const\s+)?\w+\s*(?:\[\s*\d+\s*\])?\s+(gv_\w+|gvg_\w+)\s*(?:=|;)", re.M)
GLOBAL_USE_RE = re.compile(r"\b(gv_\w+|gvg_\w+)\b")


def check_globals(text: str) -> None:
    """Refuse to emit a script that reads a global nobody declares.

    This is what a rename leaves behind. gvg_abnoName became gvg_abnoNameKey and
    three lines in the debug module kept asking for the old one, and the
    compiler's answer was "invalid args list" pointing at a string
    concatenation -- the same misleading shape as a forward reference and as a
    type-name collision, for the third distinct cause.

    Galaxy has no undeclared-identifier message worth reading, so the guard has
    to be here. It only knows the gv_/gvg_ prefixes, which is exactly the
    convention this project uses for globals and never for anything else.
    """
    stripped = re.sub(r"//[^\n]*", "", text)
    declared = set(GLOBAL_DECL_RE.findall(stripped))

    bad = {}
    for m in GLOBAL_USE_RE.finditer(stripped):
        if m.group(1) not in declared:
            bad.setdefault(m.group(1), text.count("\n", 0, m.start(1)) + 1)

    if bad:
        raise SystemExit(
            "global used but never declared -- usually the far side of a rename.\n"
            'Galaxy reports this as "invalid args list" wherever the value is\n'
            "next used, which is rarely the line you need:\n"
            + "\n".join(f"  MapScript.galaxy line {line}: {name}"
                         for name, line in sorted(bad.items())))


def main() -> int:
    if not SRC.is_dir():
        print(f"error: no source directory at {SRC}", file=sys.stderr)
        return 1

    # Regenerate the editor-derived tables first, so a rebuild always reflects
    # whatever was last saved in the editor.
    _, categories, groups, regions, upgrades = gen_objects.generate()
    print("generated src/galaxy/05_objects_gen.galaxy")
    for name, types in categories.items():
        print(f"  {name}: {', '.join(types)}")
    for name, ids in groups:
        print(f"  group '{name}': {len(ids)} objects")
    for name, rid in regions:
        print(f"  region '{name}': id {rid}")
    for u in upgrades:
        print(f"  upgrade {u['id']}: line {u['line']} lv{u['level']}"
              + (" (ally)" if u["ally"] else ""))

    # The abnormality table comes from the design docs rather than the editor,
    # so it is generated here too and its complaints are printed rather than
    # swallowed: a doc and its unit are authored on different machines, and
    # whether they agree is the one thing neither side can check alone.
    _, abnormalities, notes = gen_abnormalities.generate()
    print("generated src/galaxy/04_abno_gen.galaxy")
    for e in abnormalities:
        print(f"  abnormality {e['id']}: {e['name']}")
    for note in notes:
        print(f"  ! {note}")

    # Player-facing text last of the three, because the check it runs is against
    # the Galaxy sources rather than against the map, so it wants them final.
    gen_strings.main()

    # The editor wires its own generated scripts into MapScript.galaxy (an
    # include plus an init call). This build rewrites that file wholesale, so
    # any such wiring is dropped -- and dropping it fails silently, because an
    # un-included script is simply an unused file rather than a compile error.
    # Say so loudly instead.
    editor_scripts = sorted(p.name for p in OUT.parent.glob("ai*.galaxy"))
    if editor_scripts:
        print(
            f"warning: {', '.join(editor_scripts)} is editor-generated and will NOT be\n"
            f"         included by this build. The AI it defines will not run. Either\n"
            f"         delete the AI definition in the editor, or teach this script to\n"
            f"         emit the include and InitCustomAI().",
            file=sys.stderr,
        )

    modules = sorted(SRC.glob("*.galaxy"))
    if not modules:
        print(f"error: no .galaxy modules in {SRC}", file=sys.stderr)
        return 1

    parts = [BANNER]
    inits: list[str] = []

    for path in modules:
        body = path.read_text(encoding="utf-8")
        inits.extend(INIT_RE.findall(body))
        parts.append(
            f"//--------------------------------------------------------------------------------------------------\n"
            f"// src/galaxy/{path.name}\n"
            f"//--------------------------------------------------------------------------------------------------\n"
            f"{body.rstrip()}\n\n"
        )

    parts.append(
        "//--------------------------------------------------------------------------------------------------\n"
        "// Map Initialization\n"
        "//--------------------------------------------------------------------------------------------------\n"
        "void InitMap () {\n"
        "    libNtve_InitLib();\n"
    )
    parts.extend(f"    {name}();\n" for name in inits)
    parts.append("}\n")

    check_type_names("".join(parts))
    check_globals("".join(parts))
    check_forward_refs("".join(parts))
    OUT.write_text("".join(parts), encoding="utf-8")

    print(f"built {OUT.relative_to(ROOT)}")
    print(f"  modules: {', '.join(p.name for p in modules)}")
    print(f"  init:    {', '.join(inits) if inits else '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
