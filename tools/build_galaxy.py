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

import gen_objects

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


def main() -> int:
    if not SRC.is_dir():
        print(f"error: no source directory at {SRC}", file=sys.stderr)
        return 1

    # Regenerate the editor-derived tables first, so a rebuild always reflects
    # whatever was last saved in the editor.
    _, categories, groups = gen_objects.generate()
    print("generated src/galaxy/05_objects_gen.galaxy")
    for name, types in categories.items():
        print(f"  {name}: {', '.join(types)}")
    for name, ids in groups:
        print(f"  group '{name}': {len(ids)} objects")

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

    OUT.write_text("".join(parts), encoding="utf-8")

    print(f"built {OUT.relative_to(ROOT)}")
    print(f"  modules: {', '.join(p.name for p in modules)}")
    print(f"  init:    {', '.join(inits) if inits else '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
