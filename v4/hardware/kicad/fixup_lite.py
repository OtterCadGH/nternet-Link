#!/usr/bin/env python3
"""Post-route fixup for nlink-lite (v4.1): finish what Freerouting leaves.

  1. GND pads with no path to GND copper -> a via beside the pad (drops into
     the solid In1 plane) plus a short stub track.
  2. Two-pad signal nets left open        -> via + straight stub on each side.
  3. F.Cu / B.Cu GND pour islands holding no via -> a stitching via inside.
Every candidate via/track is checked against all other-net copper on every
layer it touches (pads as real rectangles, tracks as capsules, vias as
circles) with CLEAR mm of air, and against the board-edge/antenna fences.
Run after pour_lite.py post; then refill + DRC.
"""
import math, pcbnew

B = 'nlink-lite/nlink-lite.kicad_pcb'
X0, Y0, X1, Y1 = 50, 50, 90, 65
ANT_CLIP, EDGE = 83.4, 0.55
CLEAR, VR, TW = 0.16, 0.3, 0.2
MM, TO = pcbnew.FromMM, pcbnew.ToMM
b = pcbnew.LoadBoard(B)
LAY = {pcbnew.F_Cu: "F", pcbnew.In1_Cu: "In1", pcbnew.In2_Cu: "In2", pcbnew.B_Cu: "B"}

# ---------- obstacle model ----------------------------------------------------
items = []   # (kind, layers:set, net, geom)
for f in b.GetFootprints():
    for p in f.Pads():
        bb = p.GetBoundingBox()
        ls = {LAY[l] for l in LAY if p.IsOnLayer(l)}
        items.append(("pad", ls, p.GetNetname(),
                      (TO(bb.GetLeft()), TO(bb.GetTop()), TO(bb.GetRight()), TO(bb.GetBottom()))))
# ESP32-C3-MINI-1 exposed GND pads: vias into these are standard practice
# (module ground + thermal), so they are the ONE place via-in-pad is allowed
U1_GND_PADS = set()
for f in b.GetFootprints():
    if f.GetReference() == "U1":
        for p in f.Pads():
            if p.GetNetname() == "GND" and p.GetNumber() not in ("1", "2", "11", "14"):
                bb = p.GetBoundingBox()
                U1_GND_PADS.add((TO(bb.GetLeft()), TO(bb.GetTop()), TO(bb.GetRight()), TO(bb.GetBottom())))

def load_tracks():
    out = []
    for t in b.GetTracks():
        if isinstance(t, pcbnew.PCB_VIA):
            p = t.GetPosition()
            out.append(("via", set(LAY.values()), t.GetNetname(), (TO(p.x), TO(p.y), TO(t.GetWidth()) / 2)))
        else:
            a, e = t.GetStart(), t.GetEnd()
            out.append(("trk", {LAY.get(t.GetLayer())}, t.GetNetname(),
                        (TO(a.x), TO(a.y), TO(e.x), TO(e.y), TO(t.GetWidth()) / 2)))
    return out
items += load_tracks()

def seg_pt(ax, ay, bx, by, px, py):
    dx, dy = bx - ax, by - ay; L = dx * dx + dy * dy
    t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)
def seg_seg(a, b_, c, d):
    def o(p, q, r): return (q[0]-p[0])*(r[1]-p[1]) - (q[1]-p[1])*(r[0]-p[0])
    if o(a, b_, c) * o(a, b_, d) < 0 and o(c, d, a) * o(c, d, b_) < 0: return 0
    return min(seg_pt(*c, *d, *a), seg_pt(*c, *d, *b_), seg_pt(*a, *b_, *c), seg_pt(*a, *b_, *d))
def seg_rect(a, b_, r):
    x0, y0, x1, y1 = r
    if x0 <= a[0] <= x1 and y0 <= a[1] <= y1: return 0
    edges = [((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))]
    return min(seg_seg(a, b_, e0, e1) for e0, e1 in edges)

def shape_clear(kind, geom, layers, net, ignore=()):
    """kind 'via' geom (x,y,r) | 'trk' geom (ax,ay,bx,by,hw)"""
    for ik, ils, inet, ig in items:
        if not (ils & layers) or ig in ignore: continue
        # same-net copper is fine EXCEPT pads for vias: no via-in-pad (0402
        # solder wicking); vias keep CLEAR from every pad of any net
        if inet == net and not (kind == "via" and ik in ("pad", "via")): continue
        if inet == net and ik == "pad" and ig in U1_GND_PADS: continue
        if kind == "via":
            x, y, r = geom
            if ik == "pad": d = seg_rect((x, y), (x, y), ig)
            elif ik == "via":   # copper gap AND drill-to-drill >= 0.25 mm
                d = min(math.hypot(x - ig[0], y - ig[1]) - ig[2],
                        math.hypot(x - ig[0], y - ig[1]) - 0.3 - 0.25 + CLEAR + r)
            else: d = seg_pt(ig[0], ig[1], ig[2], ig[3], x, y) - ig[4]
            if d - r < CLEAR: return False
        else:
            ax, ay, bx, by, hw = geom
            if ik == "pad": d = seg_rect((ax, ay), (bx, by), ig)
            elif ik == "via": d = seg_pt(ax, ay, bx, by, ig[0], ig[1]) - ig[2]
            else: d = seg_seg((ax, ay), (bx, by), (ig[0], ig[1]), (ig[2], ig[3])) - ig[4]
            if d - hw < CLEAR: return False
    return True
def in_board(x, y, r):
    return X0 + EDGE + r <= x <= ANT_CLIP - r and Y0 + EDGE + r <= y <= Y1 - EDGE - r

added = {"via": 0, "trk": 0}
def add_via(x, y, net):
    v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
    v.SetWidth(MM(2 * VR)); v.SetDrill(MM(0.3)); v.SetNet(b.FindNet(net)); b.Add(v)
    items.append(("via", set(LAY.values()), net, (x, y, VR))); added["via"] += 1
def add_trk(a, e, layer, net, w=TW):
    t = pcbnew.PCB_TRACK(b); t.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
    t.SetEnd(pcbnew.VECTOR2I(MM(e[0]), MM(e[1]))); t.SetWidth(MM(w))
    t.SetLayer(layer); t.SetNet(b.FindNet(net)); b.Add(t)
    items.append(("trk", {LAY[layer]}, net, (a[0], a[1], e[0], e[1], w / 2))); added["trk"] += 1

def pad(ref, num):
    for f in b.GetFootprints():
        if f.GetReference() == ref:
            for p in f.Pads():
                if p.GetNumber() == num: return p
def pad_layer(p): return pcbnew.B_Cu if p.IsOnLayer(pcbnew.B_Cu) and not p.IsOnLayer(pcbnew.F_Cu) else pcbnew.F_Cu
def pad_xy(p): q = p.GetPosition(); return TO(q.x), TO(q.y)
def own_rect(p):
    bb = p.GetBoundingBox(); return (TO(bb.GetLeft()), TO(bb.GetTop()), TO(bb.GetRight()), TO(bb.GetBottom()))

def best_via(targets, net, search=2.2, step=0.05):
    """targets: [(pad, layer)] each gets a straight stub to the via on its layer"""
    cx = sum(pad_xy(p)[0] for p, _ in targets) / len(targets)
    cy = sum(pad_xy(p)[1] for p, _ in targets) / len(targets)
    ign = tuple(own_rect(p) for p, _ in targets)
    best = None
    n = int(search / step)
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x, y = round(cx + i * step, 3), round(cy + j * step, 3)
            if not in_board(x, y, VR): continue
            cost = sum(math.dist(pad_xy(p), (x, y)) for p, _ in targets)
            if best and cost >= best[0]: continue
            if not shape_clear("via", (x, y, VR), set(LAY.values()), net): continue
            ok = all(shape_clear("trk", (*pad_xy(p), x, y, TW / 2), {LAY[l]}, net, ignore=ign)
                     for p, l in targets)
            if ok: best = (cost, x, y)
    return best

# ---------- 1+2: open connections from the ratsnest -------------------------
# ---------- DRC-driven: whatever the router left open ------------------------
import re, tempfile
PAD_RE = re.compile(r"Pad (\S+) \[([^\]]*)\] of (\S+) on (\S+)")
def unconnected():
    tmp = tempfile.mktemp(suffix=".rpt")
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.WriteDRCReport(b, tmp, pcbnew.EDA_UNITS_MILLIMETRES, True)
    rpt = open(tmp).read()
    out = []
    for blk in rpt.split("\n[")[1:]:
        if blk.startswith("unconnected_items]"):
            out.append([l.strip() for l in blk.splitlines() if "@(" in l])
    return out

def connect_gnd_pad(p):
    got = best_via([(p, pad_layer(p))], "GND", search=2.5)
    if not got: print(f"  FAIL: no via spot beside {p.GetParent().GetReference()}.{p.GetNumber()}"); return False
    _, x, y = got; add_via(x, y, "GND"); add_trk(pad_xy(p), (x, y), pad_layer(p), "GND", 0.3)
    print(f"  GND {p.GetParent().GetReference()}.{p.GetNumber()} -> via ({x:.2f},{y:.2f})")
    return True

def gnd_islands_without_via():
    """GND pads sitting in an outer-layer pour island that holds no via"""
    gv = [(i[3][0], i[3][1]) for i in items if i[0] == "via" and i[2] == "GND"]
    hits = []
    for zi in range(b.GetAreaCount()):
        z = b.GetArea(zi)
        if z.GetIsRuleArea() or z.GetNetname() != "GND": continue
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            if not z.IsOnLayer(layer): continue
            polys = z.GetFilledPolysList(layer)
            for k in range(polys.OutlineCount()):
                ol = polys.Outline(k)
                if any(ol.PointInside(pcbnew.VECTOR2I(MM(x), MM(y))) for x, y in gv): continue
                for f in b.GetFootprints():
                    if f.GetReference() == "U1": continue   # module GND is bonded internally
                    for p in f.Pads():
                        if p.GetNetname() == "GND" and p.IsOnLayer(layer) and p.GetDrillSize().x == 0 \
                           and ol.PointInside(p.GetPosition()):
                            hits.append(p); break
    return hits

for rnd in range(4):
    left = unconnected()
    print(f"round {rnd}: {len(left)} unconnected item(s)")
    if not left: break
    progress = False
    for ent in left:
        pads = [PAD_RE.search(l) for l in ent]
        pads = [m for m in pads if m]
        if not pads:                      # zone-zone: islands without vias
            for p in gnd_islands_without_via():
                progress |= connect_gnd_pad(p)
            continue
        nets = {m.group(2) for m in pads}
        if nets == {"GND"}:
            for m in pads:
                if m.group(3) != "U1":
                    progress |= connect_gnd_pad(pad(m.group(3), m.group(1)))
        elif len(pads) == 2 and len(nets) == 1:
            net = nets.pop()
            p1, p2 = pad(pads[0].group(3), pads[0].group(1)), pad(pads[1].group(3), pads[1].group(1))
            got = best_via([(p1, pad_layer(p1)), (p2, pad_layer(p2))], net)
            if got:
                _, x, y = got; add_via(x, y, net)
                add_trk(pad_xy(p1), (x, y), pad_layer(p1), net); add_trk(pad_xy(p2), (x, y), pad_layer(p2), net)
                print(f"  {net}: via ({x:.2f},{y:.2f}) + stubs"); progress = True
            else:
                print(f"  FAIL {net}: no clear via spot")
    if not progress: break

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(B)
print(f"fixup added {added['via']} vias, {added['trk']} tracks")
