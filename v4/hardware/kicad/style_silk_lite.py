#!/usr/bin/env python3
"""Silkscreen pass for nlink-lite: functional text only, deliberately placed.

Priority (kept): J1 pigtail pin labels, back pogo-pad labels, board name.
Removed: every reference designator and value (clutter at this board size;
assembly uses the fab layer + position files).
"""
import pcbnew

B = 'nlink-lite/nlink-lite.kicad_pcb'
b = pcbnew.LoadBoard(B)
MM = pcbnew.FromMM

# --- 1. hide all reference / value texts ------------------------------------
FPS = {f.GetReference(): f for f in b.GetFootprints()}   # capture once (SWIG)
for f in FPS.values():
    f.Reference().SetVisible(False)
    f.Value().SetVisible(False)
    # also hide any extra fp_text user items (e.g. module's own labels stay:
    # the C3 module's "Antenna Area" text is useful - keep user texts)

# --- 2. idempotent: clear ALL loose silk texts, then re-add ------------------
for t in list(b.GetDrawings()):
    if isinstance(t, pcbnew.PCB_TEXT) and t.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
        b.Remove(t)

def text(s, x, y, layer, size, mirror=False, bold=False, justify=None):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(s)
    t.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
    t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(size * 0.18))
    if bold: t.SetTextThickness(MM(size * 0.25))
    b.Add(t)
    if mirror:  # native flip: moves to B.SilkS with correct mirroring
        t.Flip(t.GetPosition(), True)
    # justify is given in BOARD coords ("right" = text body extends toward -x,
    # ending at the anchor). For mirrored (back) text KiCad applies the
    # justification in the mirrored display frame, so swap it there.
    if justify:
        want = justify if not mirror else {"right": "left", "left": "right"}[justify]
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_RIGHT if want == "right"
                          else pcbnew.GR_TEXT_H_ALIGN_LEFT)
    return t

F, BK = pcbnew.F_SilkS, pcbnew.B_SilkS

# --- 3. front: board name in the open top-left, J1 pigtail labels ----------
text("nlink-lite", 59.2, 51.7, F, 1.1, bold=True)

# J1 pins after rot180 at (52,62.6): 1=62.6 VBUS, 2=60.06 D-, 3=57.52 D+,
# 4=54.98 NC, 5=52.44 GND. Labels just right of the holes.
for label, y in [("V+", 62.6), ("D-", 60.06), ("D+", 57.52), ("G", 52.44)]:
    text(label, 54.0, y, F, 0.6)

# --- 4. back: pogo legend, one line per PHYSICAL pad row ---------------------
# J4 real geometry (after flip): 3 rows x 2 cols.
#   rows y = 56.23 (pins 5,6), 57.50 (3,4), 58.77 (1,2)
#   cols x = 78.45 (even pins, LEFT in back view), 74.55 (odd pins, RIGHT)
# The area around the connector is dense copper fanout + vias, so the legend
# lives in the antenna keepout zone (x>83.4: zero copper, verified), each
# line vertically aligned with its pad row and listing the two pads of that
# row in the same left-to-right order they appear in the back view.
# justify="left" (board coords) = starts at anchor, extends +x = in the
# mirrored back view the lines are right-aligned toward the connector.
# Block centered mid-board on the GND pour (x 60.8-67.0 y 55.4-59.6 verified
# free of vias and back traces), rows still aligned with the pad rows.
text("6:D+ 5:D-",   63.95, 56.23, BK, 0.55, mirror=True)
text("4:IO0 3:EN",  63.95, 57.50, BK, 0.55, mirror=True)
text("2:GND 1:3V3", 63.95, 58.77, BK, 0.55, mirror=True)
text("PROG", 76.5, 60.4, BK, 0.7, mirror=True, bold=True)   # below connector
text("nlink-lite v4", 58.5, 52.6, BK, 1.15, mirror=True, bold=True)

b.Save(B)

# --- 5. rotate the module's own "Antenna Area" label to vertical -------------
# pcbnew's GraphicalItems() iterator is SWIG-broken in this env, so patch the
# saved file textually: free the angle ("unlocked") and shrink the font.
import re
src = open(B).read()
src = re.sub(
    r'\(fp_text user "Antenna Area" \(at [^)]*\) \(layer "F\.SilkS"\)\s*'
    r'\(effects \(font \(size [^)]*\) \(thickness [^)]*\)\)\)',
    '(fp_text user "Antenna Area" (at 0 -5.8 90 unlocked) (layer "F.SilkS")\n'
    '        (effects (font (size 0.9 0.9) (thickness 0.16)))',
    src)
open(B, "w").write(src)
print("silk restyled: refs hidden, functional labels placed, antenna text patched")
