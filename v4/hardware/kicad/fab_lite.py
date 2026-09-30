#!/usr/bin/env python3
"""Build the complete nlink-lite fab package (v4.1) from the board file.

  python3 fab_lite.py
Writes nlink-lite/gerbers/ + gerbers-nlink-lite.zip (4 copper layers, masks,
paste, silk, edge, PTH/NPTH drills + maps) and nlink-lite/assembly/:
  nlink-lite-BOM.csv  grouped BOM (JLCPCB column names + MPN/spec + notes)
  nlink-lite-CPL.csv  pick-and-place (JLCPCB column names), both sides
LCSC part numbers are left blank on purpose: pick them in the fab's part
search against the MPN/spec column. Check rotations in the fab preview.
"""
import csv, os, subprocess, zipfile, collections, pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "nlink-lite")
PCB = os.path.join(D, "nlink-lite.kicad_pcb")

# parts that are pads only (hand-soldered pigtail / pogo test pads): no BOM line
PADS_ONLY = {"J1": "mini-A plug pigtail, hand-soldered to 5 through-holes (pin 4 ID = GND)",
             "J4": "pogo programming pads, no part"}
SPEC = {  # value/footprint -> (MPN or spec, note)
    ("ESP32-C3-MINI-1-N4", "ESP32-C3-MINI-1"): ("Espressif ESP32-C3-MINI-1-N4", "PCB antenna at board edge"),
    ("CP2102N-A02-GQFN24", "QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm"): ("Silicon Labs CP2102N-A02-GQFN24R", ""),
    ("TLV62569DBV", "SOT-23-5"): ("TI TLV62569DBVR", "3.3 V buck, FB 453k/100k"),
    ("USBLC6-2SC6", "SOT-23-6"): ("ST USBLC6-2SC6", "USB ESD"),
    ("PWR_SW", "SW_SPDT_PCM12"): ("C&K PCM12SMTR", "check current rating vs ~260 mA peak"),
    ("2.2uH", "L_1210_3225Metric"): ("2.2 uH, 1210, Isat >= 1.5 A, DCR <= 100 mOhm", ""),
    ("22u", "C_0805_2012Metric"): ("22 uF 0805 X5R 10 V", "buck output"),
    ("10u", "C_0805_2012Metric"): ("10 uF 0805 X5R 16 V", "C3 on 5 V VBUS, C7 at module"),
    ("4.7u", "C_0402_1005Metric"): ("4.7 uF 0402 X5R 6.3 V", ""),
    ("100n", "C_0402_1005Metric"): ("100 nF 0402 X7R 16 V", ""),
    ("LED_STATUS", "LED_0402_1005Metric"): ("0402 LED, any color, Vf <= 2.2 V", "GPIO10 via 470R"),
}
def rspec(v): return f"{v} 0402 1% 1/16 W"

def run(*a): subprocess.run(a, check=True, capture_output=True)

# ---- gerbers + drill ---------------------------------------------------------
G = os.path.join(D, "gerbers")
os.makedirs(G, exist_ok=True)
for f in os.listdir(G): os.remove(os.path.join(G, f))
run("kicad-cli", "pcb", "export", "gerbers", "-l",
    "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,F.SilkS,B.SilkS,Edge.Cuts",
    "--subtract-soldermask", "-o", G + "/", PCB)
run("kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
    "-u", "mm", "--generate-map", "--map-format", "gerberx2", "-o", G + "/", PCB)
zp = os.path.join(D, "gerbers-nlink-lite.zip")
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(os.listdir(G)): z.write(os.path.join(G, f), f)

# ---- BOM + CPL -----------------------------------------------------------------
A = os.path.join(D, "assembly"); os.makedirs(A, exist_ok=True)
b = pcbnew.LoadBoard(PCB); TO = pcbnew.ToMM
groups = collections.OrderedDict(); cpl = []
for f in sorted(b.GetFootprints(), key=lambda f: (f.GetReference()[0], int(''.join(c for c in f.GetReference() if c.isdigit()) or 0))):
    ref, val = f.GetReference(), f.GetValue()
    fpn = str(f.GetFPID().GetLibItemName())
    if ref in PADS_ONLY: continue
    mpn, note = SPEC.get((val, fpn), (rspec(val) if ref.startswith("R") else "?", ""))
    groups.setdefault((val, fpn, mpn, note), []).append(ref)
    pos = f.GetPosition()
    cpl.append([ref, f"{TO(pos.x):.4f}mm", f"{-TO(pos.y):.4f}mm",
                "Bottom" if f.IsFlipped() else "Top", f"{f.GetOrientationDegrees() % 360:g}"])
with open(os.path.join(A, "nlink-lite-BOM.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["Comment", "Designator", "Footprint", "Qty", "MPN / spec", "LCSC", "Notes"])
    for (val, fpn, mpn, note), refs in groups.items():
        w.writerow([val, ",".join(refs), fpn, len(refs), mpn, "", note])
    for r, why in PADS_ONLY.items():
        w.writerow(["DNP", r, "", 0, "", "", why])
with open(os.path.join(A, "nlink-lite-CPL.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"]); w.writerows(cpl)
unknown = [r for (v, fp, m, n), rs in groups.items() if m == "?" for r in rs]
print(f"gerbers: {len(os.listdir(G))} files -> {os.path.basename(zp)}")
print(f"BOM: {len(groups)} lines, {sum(len(r) for r in groups.values())} placed parts; CPL: {len(cpl)} rows")
if unknown: raise SystemExit(f"BOM has parts with no spec: {unknown}")
