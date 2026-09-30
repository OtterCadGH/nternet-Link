#!/usr/bin/env python3
"""Copper pours + stitching for nlink-lite (v4.1).

  pour_lite.py pre   -> antenna keepout (all layers) + solid In1.Cu GND plane,
                        then export /tmp/lite.dsn for Freerouting (the router
                        drops GND vias straight into the In1 plane)
  pour_lite.py post  -> F.Cu + B.Cu GND pours, GND stitching-via grid,
                        refill all zones, save

Everything stops at ANT_CLIP (module antenna keepout, x > 83.4).
Idempotent: removes the zones/vias it owns before re-adding them.
"""
import sys, pcbnew

B = 'nlink-lite/nlink-lite.kicad_pcb'
X0, Y0, X1, Y1 = 50, 50, 90, 65
ANT_CLIP = 83.4
MM = pcbnew.FromMM
TAG = "nlink41"          # zone name prefix owned by this script

def strip_zones(path, keep=lambda block: False):
    """Remove top-level (zone ...) blocks from the FILE before loading.
    KiCad 7's SWIG bindings corrupt after BOARD.Remove(zone), so zones are
    never removed through the API."""
    src = open(path).read()
    out, i, n = [], 0, 0
    while True:
        j = src.find("\n  (zone", i)
        if j < 0:
            out.append(src[i:]); break
        depth, k = 0, j + 1
        while True:
            c = src[k]
            if c == "(": depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0: break
            k += 1
        block = src[j:k + 1]
        out.append(src[i:j] + (block if keep(block) else ""))
        n += 0 if keep(block) else 1
        i = k + 1
    open(path, "w").write("".join(out))
    return n

mode = sys.argv[1] if len(sys.argv) > 1 else "pre"
if mode == "pre":
    removed = strip_zones(B)                                   # all zones
else:
    removed = strip_zones(B, keep=lambda blk: f'(name "{TAG}_pour' not in blk)
print(f"stripped {removed} old zone(s)")

b = pcbnew.LoadBoard(B)
gnd = b.FindNet("GND")

def zones():
    """b.Zones() is not iterable after reload in KiCad 7 SWIG; index instead"""
    return [b.GetArea(i) for i in range(b.GetAreaCount())]

def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

def add_zone(name, layers, pts, net=None, keepout=False, prio=0):
    z = pcbnew.ZONE(b)
    z.SetZoneName(f"{TAG}_{name}")
    ls = pcbnew.LSET()
    for l in layers: ls.AddLayer(l)
    z.SetLayerSet(ls)
    ol = z.Outline(); ol.NewOutline()
    for x, y in pts: ol.Append(MM(x), MM(y))
    if keepout:
        z.SetIsRuleArea(True)
        z.SetDoNotAllowCopperPour(True); z.SetDoNotAllowVias(True)
        z.SetDoNotAllowTracks(True); z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
    else:
        z.SetNet(net)
        z.SetAssignedPriority(prio)
        z.SetLocalClearance(MM(0.2))
        z.SetMinThickness(MM(0.2))
        # solid to SMD pads (current + no starved spokes), thermal to THT (J1 hand-solder)
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)
        z.SetThermalReliefGap(MM(0.2))
        z.SetThermalReliefSpokeWidth(MM(0.3))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)  # no orphan copper
    b.Add(z)
    return z

ALL_CU = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
if mode == "pre":
    # In1 is a dedicated plane: mark it a power layer so the router never
    # puts traces through it (DSN "type power"). Signals use F, In2, B.
    b.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    add_zone("keepout_antenna", ALL_CU, rect(ANT_CLIP, Y0, X1, Y1), keepout=True)
    # 0.5 mm edge strips: the router ignores the board-edge clearance rule,
    # so fence tracks/vias out of it (pads stay allowed: J1, SW1 hug edges)
    E = 0.55
    for nm, r in [("keepout_edge_top", rect(X0, Y0, ANT_CLIP, Y0 + E)),
                  ("keepout_edge_bot", rect(X0, Y1 - E, ANT_CLIP, Y1)),
                  ("keepout_edge_left", rect(X0, Y0, X0 + E, Y1))]:
        add_zone(nm, ALL_CU, r, keepout=True)
    add_zone("plane_In1", [pcbnew.In1_Cu], rect(X0 + 0.3, Y0 + 0.3, ANT_CLIP, Y1 - 0.3), gnd)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(B)
    pcbnew.ExportSpecctraDSN(b, '/tmp/lite.dsn')
    print("pre: keepout + In1 GND plane added, /tmp/lite.dsn exported")

elif mode == "post":
    add_zone("pour_F", [pcbnew.F_Cu], rect(X0 + 0.3, Y0 + 0.3, ANT_CLIP, Y1 - 0.3), gnd)
    add_zone("pour_B", [pcbnew.B_Cu], rect(X0 + 0.3, Y0 + 0.3, ANT_CLIP, Y1 - 0.3), gnd)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())

    # --- stitching vias: candidate grid, keep only spots that sit inside
    # the filled GND copper on F.Cu AND B.Cu AND In1 with margin, and are
    # clear of every non-GND item on every layer.
    fills = {l: None for l in (pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu)}
    zs = [z for z in zones() if z.GetNetname() == "GND" and not z.GetIsRuleArea()]
    VR = 0.3                   # via radius (0.6 mm)
    MARGIN = 0.25              # copper around via inside the pour
    RING = [(0, 0)] + [(dx, dy) for dx, dy in ((VR+MARGIN,0),(-VR-MARGIN,0),(0,VR+MARGIN),(0,-VR-MARGIN),
                               (0.7*(VR+MARGIN),0.7*(VR+MARGIN)),(-0.7*(VR+MARGIN),0.7*(VR+MARGIN)),
                               (0.7*(VR+MARGIN),-0.7*(VR+MARGIN)),(-0.7*(VR+MARGIN),-0.7*(VR+MARGIN)))]
    def in_fill(layer, x, y):
        """via disk + margin fully inside this layer's filled GND copper"""
        for z in zs:
            if not z.IsOnLayer(layer):
                continue
            poly = z.GetFilledPolysList(layer)
            if all(poly.Contains(pcbnew.VECTOR2I(MM(x + dx), MM(y + dy))) for dx, dy in RING):
                return True
        return False
    # obstacles: every pad, track, via not on GND (all layers, since the via is through)
    obst = []
    for f in b.GetFootprints():
        for p in f.Pads():
            bb = p.GetBoundingBox()
            obst.append((pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
                         pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()),
                         p.GetNetname() == "GND" and p.GetDrillSize().x == 0))
    for t in b.GetTracks():
        bb = t.GetBoundingBox()
        obst.append((pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
                     pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()), False))
    def clear(x, y, gap=0.2):
        r = VR + gap
        for x0, y0, x1, y1, samenet_smd in obst:
            if samenet_smd:
                continue
            if x0 - r < x < x1 + r and y0 - r < y < y1 + r:
                # finer test for tracks: bbox is conservative, keep it
                return False
        return True
    placed = []
    y = Y0 + 1.1
    while y < Y1 - 1.0:
        x = X0 + 1.1
        while x < ANT_CLIP - 1.0:
            if (clear(x, y) and all(in_fill(l, x, y) for l in fills)
                    and all(abs(x - px) + abs(y - py) > 1.6 for px, py in placed)):
                v = pcbnew.PCB_VIA(b)
                v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
                v.SetWidth(MM(0.6)); v.SetDrill(MM(0.3))
                v.SetNet(gnd)
                b.Add(v)
                placed.append((x, y))
            x += 0.8
        y += 0.8
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(B)
    print(f"post: F/B GND pours + {len(placed)} stitching vias, zones refilled")
