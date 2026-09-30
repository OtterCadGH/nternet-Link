#!/usr/bin/env python3
"""nlink-lite release gate (v4.1). Fails (exit 1) on any regression of the
2026-09-23 hardware audit. Run from v4/hardware/kicad after the build:

  kicad-cli sch export netlist -o /tmp/nlink-lite.net nlink-lite/nlink-lite.kicad_sch
  python3 verify_netlists.py && python3 check_lite.py
"""
import math, re, sys, pcbnew

B = 'nlink-lite/nlink-lite.kicad_pcb'
NET = '/tmp/nlink-lite.net'
TO = pcbnew.ToMM
fails = 0
def check(cond, msg):
    global fails
    print(("ok:   " if cond else "FAIL: ") + msg)
    fails += 0 if cond else 1

b = pcbnew.LoadBoard(B)
pads = {(f.GetReference(), p.GetNumber()): p for f in b.GetFootprints() for p in f.Pads()}
def net(r, n): p = pads.get((r, n)); return p.GetNetname() if p else None

# --- schematic <-> PCB sync: every schematic node lands on the same PCB net --
txt = open(NET).read()
sch = {}
chunks = re.split(r'\(net \(code "\d+"\) \(name "([^"]+)"\)', txt)  # same parse as verify_netlists.py
for i in range(1, len(chunks), 2):
    name, body = chunks[i], chunks[i + 1]
    for ref, pin in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)', body):
        sch[(ref, pin)] = None if name.startswith("unconnected-") else name.lstrip("/")
check(len(sch) > 100, f"schematic netlist parsed ({len(sch)} nodes)")
sch_refs = {r for r, _ in sch}
pcb_refs = {r for r, _ in pads}
check(sch_refs == pcb_refs, f"same parts in schematic and PCB ({len(sch_refs)} vs {len(pcb_refs)})"
      + ("" if sch_refs == pcb_refs else f" diff {sorted(sch_refs ^ pcb_refs)}"))
mism = [(k, v, net(*k)) for k, v in sch.items() if (v or "") != (net(*k) or "")]
check(not mism, f"every pad's net matches the schematic ({len(sch)} nodes)"
      + ("" if not mism else f" first: {mism[:4]}"))

# --- audit items --------------------------------------------------------------
check(net("J1", "4") == "GND", "J1 pin 4 (ID) grounded -> Nspire host mode")
check(net("U3", "8") == "CP_VBUS" and {net("R2", "1"), net("R2", "2")} == {"VBUS", "CP_VBUS"}
      and {net("R3", "1"), net("R3", "2")} == {"CP_VBUS", "GND"},
      "CP2102N VBUS sense via 22.1k/47.5k divider")
vals = {f.GetReference(): f.GetValue() for f in b.GetFootprints()}
check(vals.get("R2") == "22.1k" and vals.get("R3") == "47.5k", "divider values 22.1k / 47.5k")
check(net("U1", "23") == "BOOT" and net("J4", "4") == "BOOT", "BOOT strap = GPIO9 -> prog pad 4")
check(not net("U1", "12"), "GPIO0 unused")
check(net("U1", "16") == "STATUS_LED", "status LED on GPIO10")
check(net("U1", "22") == "IO8_STRAP" and net("U1", "5") == "IO2_STRAP", "GPIO8 + GPIO2 pulled up")
u = pads[("U1", "3")].GetPosition()
dmin = min(math.dist((TO(u.x), TO(u.y)), (TO(p.GetPosition().x), TO(p.GetPosition().y)))
           for (r, n), p in pads.items() if r.startswith("C") and p.GetNetname() == "+3V3")
check(dmin <= 2.5, f"decoupling within 2.5 mm of U1 3V3 pin ({dmin:.2f} mm)")
cap = sum(float(vals[r].replace("u", "e-6").replace("n", "e-9"))
          for (r, n), p in pads.items() if r.startswith("C") and n == "1" and p.GetNetname() == "+3V3") * 1e6
check(10 <= cap <= 47, f"+3V3 capacitance {cap:.1f} uF inside TLV62569 10-47 uF")

check(vals.get("R1") == "1k" and net("R1", "2") == "CP_RSTn", "CP2102N RSTb pull-up 1k (datasheet)")
# footprint-owned zones must sit on the board (v4.0 had the module's antenna
# keepout at x 155-168 mm, far off the 50-90 mm outline)
X0, Y0, X1, Y1 = 50, 50, 90, 65
for f in b.GetFootprints():
    for z in f.Zones():
        ol = z.Outline()
        xs = [TO(ol.CVertex(k).x) for k in range(ol.TotalVertices())]
        ys = [TO(ol.CVertex(k).y) for k in range(ol.TotalVertices())]
        check(X0 <= min(xs) and max(xs) <= X1 and Y0 <= min(ys) and max(ys) <= Y1,
              f"{f.GetReference()} footprint zone '{z.GetZoneName()}' on the board "
              f"(x {min(xs):.1f} to {max(xs):.1f}, y {min(ys):.1f} to {max(ys):.1f})")
        if f.GetReference() == "U1":
            check(min(xs) >= 83.05, "U1 antenna keepout starts past the module's last pad (83.05)")

tracks = list(b.GetTracks())
segs = [t for t in tracks if not isinstance(t, pcbnew.PCB_VIA)]
vias = [t for t in tracks if isinstance(t, pcbnew.PCB_VIA)]
check(not [s for s in segs if s.GetLayer() == pcbnew.In1_Cu], "no tracks on In1 (solid plane)")
zones = [b.GetArea(i) for i in range(b.GetAreaCount())]
check(any(z.IsOnLayer(pcbnew.In1_Cu) and z.GetNetname() == "GND" and not z.GetIsRuleArea() for z in zones),
      "In1 GND plane zone present")
ng = sum(1 for v in vias if v.GetNetname() == "GND")
check(ng >= 15, f"GND stitching: {ng} vias (>= 15)")
thin = [s for s in segs if s.GetNetname() in ("VBUS", "VBUS_IN", "+3V3", "SW_NODE") and TO(s.GetWidth()) < 0.39]
check(not thin, f"power tracks >= 0.4 mm ({len(thin)} thinner)")
check(not [s for s in segs if max(TO(s.GetStart().x), TO(s.GetEnd().x)) > 83.4]
      and not [v for v in vias if TO(v.GetPosition().x) > 83.4], "antenna zone copper-free")

# --- KiCad DRC -----------------------------------------------------------------
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.WriteDRCReport(b, '/tmp/drc_check.rpt', pcbnew.EDA_UNITS_MILLIMETRES, True)
rpt = open('/tmp/drc_check.rpt').read()
cats = re.findall(r'^\[(\w+)\]', rpt, re.M)
unc = int(re.search(r'Found (\d+) unconnected', rpt).group(1))
check(unc == 0, f"DRC: 0 unconnected pads ({unc})")
for bad in ("clearance", "shorting_items", "tracks_crossing", "hole_near_hole", "hole_clearance",
            "via_diameter", "annular_width", "track_width"):
    n = cats.count(bad)
    check(n == 0, f"DRC: 0 {bad} ({n})")
# accepted, carried over from v4.0 placement (documented in PCB-DESIGN.md)
KNOWN = {"copper_edge_clearance": 4, "courtyards_overlap": 2, "text_height": 8, "silk_over_copper": 1}
for k, lim in KNOWN.items():
    check(cats.count(k) <= lim, f"DRC: {k} {cats.count(k)} <= accepted {lim}")
print(f"\n{'FAILURES: ' + str(fails) if fails else 'nlink-lite release gate PASSED'}")
sys.exit(1 if fails else 0)
