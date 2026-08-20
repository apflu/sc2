#!/usr/bin/env python3
"""Print the map's floor plan as text.

The terrain is not opaque. Three of the files under the map say everything a
reader needs and two of them are plain XML:

    t3Terrain.xml       dimensions, tileset, and a <cliffCellList> of every
                        cliff cell at HALF resolution (96x96 over 192x192)
    t3SyncCliffLevel    CLIF, 32-byte header, then one uint16 per terrain cell.
                        The value is the cliff level times 64, so 0 / 64 / 128
                        are levels 0 / 1 / 2
    t3CellFlags         LFCT, 32-byte header, then one byte per terrain cell.
                        Bit 0 is set on everything that cannot be walked on

Everything else -- t3TextureMasks at nine megabytes, t3VertCol, the height map
-- is paint and micro-relief, and none of it changes what the game is played
on. This reads the two that matter and draws them.

Which is worth having as a tool rather than a one-off, because the alternative
is asking somebody to describe their own map: this map is an interior, the
rooms are made of cliff, and "is there a wall between these two things" is a
question that comes up constantly and has an exact answer sitting in a file.

    python3 tools/show_terrain.py                whole playable area
    python3 tools/show_terrain.py --plain        terrain only, no overlay
    python3 tools/show_terrain.py --at 44 80 --span 40
"""

import argparse
import struct
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "LobotomyShiphold.SC2Map"

VOID = " "
BLOCKED = "#"
LEVEL = {1: ".", 2: "+", 3: "^"}

# One letter per placed thing. Ordered so that the specific prefixes win over
# the general ones -- Lob_CoreDown before Lob_Core, and so on.
MARKS = [
    ("ContainGateControl", "P"),
    ("ContainGate", "D"),
    ("Lob_CoreDown", "c"),
    ("Lob_Core", "C"),
    ("Lob_DeviceDown", "e"),
    ("Lob_Device", "E"),
    ("Lob_Hero", "H"),
    ("Lob_SCV", "W"),
    ("Lob_Turret", "T"),
    ("Lob_Recycler", "R"),
    ("Lob_Pile", "O"),
    ("Lob_Debris", "B"),
    ("Lob_Marker", "M"),
    ("Lob_Ordeal", "!"),
    ("Lob_Emp", "w"),
]


def mark_for(unit_type: str) -> str:
    for prefix, ch in MARKS:
        if unit_type.startswith(prefix):
            return ch
    # An abnormality is named after its document (O_03_03), not after a prefix,
    # so it is what is left once everything with a prefix has been claimed.
    return "A"


def read_dims() -> tuple[int, int]:
    root = ET.parse(MAP / "t3Terrain.xml").getroot()
    hm = root.find("heightMap")
    vx, vy = (int(n) for n in hm.get("dim").split())
    # dim counts VERTICES; cells are one fewer in each direction.
    return vx - 1, vy - 1


def read_grid(name: str, magic: bytes, stride: int, w: int, h: int) -> list[int]:
    raw = (MAP / name).read_bytes()
    if raw[:4] != magic:
        raise SystemExit(f"{name}: expected magic {magic!r}, found {raw[:4]!r}")
    body = raw[32:]
    want = w * h * stride
    if len(body) != want:
        raise SystemExit(f"{name}: {len(body)} bytes of data, expected {want} "
                         f"for {w}x{h} at {stride} each")
    if stride == 1:
        return list(body)
    return list(struct.unpack_from("<%dH" % (w * h), body))


def read_bounds() -> tuple[int, int, int, int]:
    """The playable rectangle, out of MapInfo.

    Read positionally rather than by parsing the whole record: the four ints
    sit together after the tileset name, and they are the only four in that
    stretch that describe a rectangle inside the map. Falls back to the whole
    map, which is never wrong, only wider.
    """
    raw = (MAP / "MapInfo").read_bytes()
    w = struct.unpack_from("<I", raw, 16)[0]
    h = struct.unpack_from("<I", raw, 20)[0]
    for off in range(24, len(raw) - 16):
        l, b, r, t = struct.unpack_from("<4i", raw, off)
        if 0 <= l < r <= w and 0 <= b < t <= h and (r - l) > 16 and (t - b) > 16:
            return l, b, r, t
    return 0, 0, w, h


def read_objects() -> list[tuple[float, float, str]]:
    path = MAP / "Objects"
    if not path.is_file():
        return []
    out = []
    for obj in ET.parse(path).getroot().iter("ObjectUnit"):
        pos = obj.get("Position")
        if not pos:
            continue
        x, y = (float(v) for v in pos.split(",")[:2])
        out.append((x, y, obj.get("UnitType", "?")))
    return out


def read_regions() -> list[tuple[str, float, float, float, float]]:
    path = MAP / "Regions"
    if not path.is_file():
        return []
    out = []
    for region in ET.parse(path).getroot().iter("region"):
        name = region.find("name")
        quad = region.find("./shape/quad")
        if name is None or quad is None:
            continue
        x0, y0, x1, y1 = (float(v) for v in quad.get("value").split(","))
        out.append(((name.get("value") or "").strip(), x0, y0, x1, y1))
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plain", action="store_true", help="terrain only")
    ap.add_argument("--at", nargs=2, type=float, metavar=("X", "Y"),
                    help="centre on this world point")
    ap.add_argument("--span", type=int, default=0,
                    help="how many cells across, with --at")
    args = ap.parse_args()

    w, h = read_dims()
    level = read_grid("t3SyncCliffLevel", b"CLIF", 2, w, h)
    flags = read_grid("t3CellFlags", b"LFCT", 1, w, h)

    grid = []
    for y in range(h):
        row = []
        for x in range(w):
            i = y * w + x
            lv = level[i] // 64
            if lv == 0:
                row.append(VOID)
            elif flags[i] & 1:
                row.append(BLOCKED)
            else:
                row.append(LEVEL.get(lv, "?"))
        grid.append(row)

    regions = read_regions()
    marks: dict[tuple[int, int], str] = {}
    if not args.plain:
        # Regions first, so a unit standing in one still shows as the unit.
        for n, (name, x0, y0, x1, y1) in enumerate(regions):
            for y in range(max(0, int(y0)), min(h, int(y1) + 1)):
                for x in range(max(0, int(x0)), min(w, int(x1) + 1)):
                    if grid[y][x] in (".", "+"):
                        grid[y][x] = str(n + 1)
        for x, y, unit_type in read_objects():
            cx, cy = int(x), int(y)
            if 0 <= cx < w and 0 <= cy < h:
                marks[(cx, cy)] = mark_for(unit_type)

    if args.at:
        span = args.span or 48
        cx, cy = int(args.at[0]), int(args.at[1])
        left, right = max(0, cx - span // 2), min(w, cx + span // 2)
        bottom, top = max(0, cy - span // 4), min(h, cy + span // 4)
    else:
        left, bottom, right, top = read_bounds()

    # Two cells per printed row, one per column: a terminal cell is about twice
    # as tall as it is wide, so this comes out roughly square.
    print(f"{w}x{h} cells, showing x {left}..{right}  y {bottom}..{top}"
          + ("" if args.plain else "  (1 col = 1 cell, 1 row = 2 cells)"))
    # Every OTHER row is printed, so an object on a skipped row would simply
    # not exist. Two-cell-tall rows are the only way the plan comes out square
    # in a terminal, and a unit vanishing because it stood on an odd y is the
    # kind of quiet lie this whole tool is meant to replace -- so the skipped
    # row's marks are folded into the one above it.
    for y in range(top - 1, bottom - 1, -2):
        row = list(grid[y])
        for cy in (y - 1, y):
            if cy < 0:
                continue
            for x in range(left, right):
                ch = marks.get((x, cy))
                if ch is not None:
                    row[x] = ch
        print("%4d %s" % (y, "".join(row[left:right])))

    print()
    print(f"  {VOID}=off-ship  {BLOCKED}=wall or cliff  .=deck  +=raised deck")
    if not args.plain:
        for n, (name, x0, y0, x1, y1) in enumerate(regions):
            print(f"  {n + 1}={name}  ({x0:.0f},{y0:.0f})-({x1:.0f},{y1:.0f})")
        seen = {}
        for x, y, unit_type in read_objects():
            seen.setdefault(mark_for(unit_type), set()).add(unit_type)
        for ch in sorted(seen):
            print(f"  {ch}={', '.join(sorted(seen[ch]))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
