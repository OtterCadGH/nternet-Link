#!/usr/bin/env python3
"""Finish nlink-lite placement: flip back-side parts, verify geometry.

Checks (hard failures print FAIL and exit 1):
  1. U1 antenna end points +x (auto-corrects rotation if not).
  2. No courtyard overlaps among same-side footprints.
  3. Through-holes (incl. TC2030 NPTH) clear of all opposite-side pads.
  4. All courtyards inside the board outline (antenna may touch right edge).
Saves the board and exports /tmp/lite.dsn for routing.
"""
import sys, pcbnew

BOARD_PATH = 'nlink-lite/nlink-lite.kicad_pcb'
BACK_SET = {"J4", "R4", "C6", "R5"}
X0, Y0, X1, Y1 = 50, 50, 90, 65

def mm(v): return pcbnew.ToMM(v)

b = pcbnew.LoadBoard(BOARD_PATH)
fps = {f.GetReference(): f for f in b.GetFootprints()}
fails = []

# --- 1. antenna orientation --------------------------------------------------
u1 = fps["U1"]
pads_x = [mm(p.GetPosition().x) for p in u1.Pads()]
cx = mm(u1.GetPosition().x)
# pads centroid should be LEFT of center (antenna is the pad-free +x end)
centroid = sum(pads_x) / len(pads_x)
if centroid > cx:
    print(f"antenna points -x (pad centroid {centroid:.1f} vs cx {cx:.1f}); rotating 180")
    u1.SetOrientationDegrees(u1.GetOrientationDegrees() + 180)
    pads_x = [mm(p.GetPosition().x) for p in u1.Pads()]
    centroid = sum(pads_x) / len(pads_x)
print(f"U1 pad centroid x={centroid:.1f} (center {cx:.1f}) -> antenna at +x: {centroid < cx}")
print(f"U1 pad x extent: {min(pads_x):.1f}..{max(pads_x):.1f} (pour clip must be >= {max(pads_x):.1f})")

# --- 2. flip back set --------------------------------------------------------
for ref in BACK_SET:
    f = fps[ref]
    if f.GetLayer() != pcbnew.B_Cu:
        f.Flip(f.GetPosition(), False)   # flip in place around its own position
print("back set on B.Cu:", all(fps[r].GetLayer() == pcbnew.B_Cu for r in BACK_SET))

# --- 3. courtyard overlap check (same side) ---------------------------------
def court_bbox(f):
    side = pcbnew.F_CrtYd if f.GetLayer() == pcbnew.F_Cu else pcbnew.B_CrtYd
    c = f.GetCourtyard(side)
    if c.OutlineCount() == 0:
        return f.GetBoundingBox(False, False)  # no texts
    return c.BBox()

items = []
for ref, f in fps.items():
    bbx = court_bbox(f)
    items.append((ref, f.GetLayer(), mm(bbx.GetLeft()), mm(bbx.GetTop()),
                  mm(bbx.GetRight()), mm(bbx.GetBottom())))
for i in range(len(items)):
    for j in range(i + 1, len(items)):
        r1, l1, a, bt, c, d = items[i]
        r2, l2, e, ft, g, h = items[j]
        if l1 != l2:
            continue
        ox = min(c, g) - max(a, e)
        oy = min(d, h) - max(bt, ft)
        if ox > 0.05 and oy > 0.05:
            fails.append(f"courtyard overlap {r1} vs {r2} ({ox:.2f}x{oy:.2f}mm)")

# --- 4. through-holes vs opposite-side pads ---------------------------------
holes = []          # (ref, x, y, radius) of every drilled hole
for ref, f in fps.items():
    for p in f.Pads():
        drill = p.GetDrillSize().x
        if drill > 0:
            pos = p.GetPosition()
            holes.append((ref, mm(pos.x), mm(pos.y), mm(drill) / 2))
smd_pads = []       # (ref, layer, x, y, halfw, halfh)
for ref, f in fps.items():
    for p in f.Pads():
        if p.GetDrillSize().x == 0:
            pos, size = p.GetPosition(), p.GetSize()
            smd_pads.append((ref, f.GetLayer(), mm(pos.x), mm(pos.y),
                             mm(size.x) / 2, mm(size.y) / 2))
for href, hx, hy, hr in holes:
    hlayer = fps[href].GetLayer()
    for pref, playr, px, py, hw, hh in smd_pads:
        if pref == href or playr == hlayer:
            continue   # only opposite-side conflicts matter for a hole
        dx, dy = abs(hx - px), abs(hy - py)
        if dx < hw + hr + 0.2 and dy < hh + hr + 0.2:
            fails.append(f"hole of {href} at ({hx:.1f},{hy:.1f}) r{hr:.2f} "
                         f"hits {pref} pad on other side")

# --- 5. outline containment --------------------------------------------------
for ref, layer, a, bt, c, d in items:
    slack = 0.35 if ref == "U1" else 0.05   # antenna may kiss the edge
    if a < X0 - slack or c > X1 + slack or bt < Y0 - slack or d > Y1 + slack:
        fails.append(f"{ref} outside outline: x {a:.1f}..{c:.1f} y {bt:.1f}..{d:.1f}")

b.Save(BOARD_PATH)   # always persist flips/rotation so later passes see them
if fails:
    print("\n".join("FAIL: " + f for f in fails))
    print("saved board WITH failures (flips persisted)")
    sys.exit(1)

pcbnew.ExportSpecctraDSN(b, '/tmp/lite.dsn')
print("ALL GEOMETRY CHECKS PASS — saved board + exported /tmp/lite.dsn")
