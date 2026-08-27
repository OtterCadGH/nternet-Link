#!/usr/bin/env python3
"""nlink-lite: compact 40x15mm stick, clean placement, ready for full routing.

Layout (left -> right): mini-USB plug pads | power switch + ESD | CP2102N
bridge | buck cluster | passives rows | ESP32-C3-MINI-1 with antenna at the
right board edge. TC2030 programming pads + strap pulls live on the BACK
(flipped by finish_lite.py, which also verifies hole/pad conflicts).

Coordinates chosen against measured courtyards; finish_lite.py verifies:
courtyard overlaps, NPTH-through-hole vs front pads, outline containment.
"""
import os, uuid, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("bb", os.path.join(HERE, "build_board.py"))
bb = importlib.util.module_from_spec(spec); spec.loader.exec_module(bb)

FP_DIRS = ["/usr/share/kicad/footprints", os.path.join(HERE, "lib")]
def load_fp(lib, name):
    for d in FP_DIRS:
        p = f"{d}/{lib}.pretty/{name}.kicad_mod"
        if os.path.exists(p): return open(p).read()
    raise FileNotFoundError(f"{lib}:{name}")
bb.load_footprint = load_fp

def U(): return str(uuid.uuid4())

# Board: x 50..90, y 50..65 (40 x 15 mm). Antenna zone: x > ANT_CLIP.
BOARD = (50, 50, 90, 65)
ANT_CLIP = 83.4      # GND pours stop here (module antenna keepout)

C3_GND = {str(n): "GND" for n in
          [1, 2, 11, 14, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48,
           49, 50, 51, 52, 53]}

# BACK_SET refs get flipped to B.Cu by finish_lite.py
BACK_SET = ["J4", "R4", "C6", "R5"]

PARTS = [
    # calculator plug (through-hole pads for the mini-B pigtail)
    ("J1", "USB_MiniB_PLUG_to_calc", "Connector_PinHeader_2.54mm",
     "PinHeader_1x05_P2.54mm_Vertical", (52, 62.6), 180,
     {"1": "VBUS_IN", "2": "CALC_DM", "3": "CALC_DP", "5": "GND"}),
    # power switch on the top edge, actuator outward
    ("SW1", "PWR_SW", "Button_Switch_SMD", "SW_SPDT_PCM12", (58.6, 62.0), 180,
     {"1": "VBUS", "2": "VBUS_IN"}),
    # ESD straight in the USB path between plug and bridge
    ("U5", "USBLC6-2SC6", "Package_TO_SOT_SMD", "SOT-23-6", (56.5, 57.2), 0,
     {"1": "CALC_DM", "6": "CALC_DM", "3": "CALC_DP", "4": "CALC_DP",
      "5": "VBUS", "2": "GND"}),
    ("U3", "CP2102N-A02-GQFN24", "Package_DFN_QFN",
     "QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm", (62.5, 57.5), 0,
     {"3": "CALC_DP", "4": "CALC_DM", "8": "VBUS", "5": "+3V3", "6": "+3V3",
      "7": "+3V3", "9": "CP_RSTn", "20": "UART_TX", "21": "UART_RX",
      "2": "GND", "25": "GND"}),
    # aligned top passive row (y = 52.3)
    ("R1", "10k", "Resistor_SMD", "R_0402_1005Metric", (64.5, 52.3), 0,
     {"1": "+3V3", "2": "CP_RSTn"}),
    ("C1", "100n", "Capacitor_SMD", "C_0402_1005Metric", (66.5, 52.3), 0,
     {"1": "+3V3", "2": "GND"}),
    ("C2", "4.7u", "Capacitor_SMD", "C_0402_1005Metric", (68.5, 52.3), 0,
     {"1": "+3V3", "2": "GND"}),
    ("R6", "470", "Resistor_SMD", "R_0402_1005Metric", (70.5, 52.3), 0,
     {"1": "STATUS_LED", "2": "LED_A"}),
    ("D1", "LED_STATUS", "LED_SMD", "LED_0402_1005Metric", (70.8, 54.0), 0,
     {"1": "GND", "2": "LED_A"}),
    # buck cluster, bottom band
    ("C3", "10u", "Capacitor_SMD", "C_0805_2012Metric", (63.5, 62.4), 90,
     {"1": "VBUS", "2": "GND"}),
    ("U4", "TLV62569DBV", "Package_TO_SOT_SMD", "SOT-23-5", (66.7, 62.4), 0,
     {"4": "VBUS", "1": "VBUS", "2": "GND", "3": "SW_NODE", "5": "FB_3V3"}),
    ("L1", "2.2uH", "Inductor_SMD", "L_1210_3225Metric", (70.0, 62.3), 90,
     {"1": "SW_NODE", "2": "+3V3"}),
    ("R2", "453k", "Resistor_SMD", "R_0402_1005Metric", (66.2, 59.3), 0,
     {"1": "+3V3", "2": "FB_3V3"}),
    ("R3", "100k", "Resistor_SMD", "R_0402_1005Metric", (67.8, 59.3), 0,
     {"1": "FB_3V3", "2": "GND"}),
    ("C4", "22u", "Capacitor_SMD", "C_0805_2012Metric", (70.5, 58.6), 90,
     {"1": "+3V3", "2": "GND"}),
    ("C5", "10u", "Capacitor_SMD", "C_0805_2012Metric", (70.8, 55.9), 90,
     {"1": "+3V3", "2": "GND"}),
    # module: rot set so antenna points +x; finish_lite.py verifies direction
    ("U1", "ESP32-C3-MINI-1-N4", "Espressif", "ESP32-C3-MINI-1", (80.8, 57.4), 90,
     {"3": "+3V3", "8": "EN", "12": "IO0", "22": "STATUS_LED",
      "21": "UART_TX", "20": "UART_RX", "26": "USB_DM", "27": "USB_DP",
      **C3_GND}),
    # back-side set (flipped by finish_lite.py)
    ("J4", "PROG_PADS_2x3_POGO", "Connector_PinHeader_1.27mm",
     "PinHeader_2x03_P1.27mm_Vertical_SMD", (76.5, 57.5), 0,
     {"1": "+3V3", "2": "GND", "3": "EN", "4": "IO0",
      "5": "USB_DM", "6": "USB_DP"}),
    ("R4", "10k", "Resistor_SMD", "R_0402_1005Metric", (74, 53.5), 0,
     {"1": "+3V3", "2": "EN"}),
    ("C6", "100n", "Capacitor_SMD", "C_0402_1005Metric", (76, 53.5), 0,
     {"1": "EN", "2": "GND"}),
    ("R5", "10k", "Resistor_SMD", "R_0402_1005Metric", (78, 53.5), 0,
     {"1": "+3V3", "2": "IO0"}),
]

def build(out=None):
    netnames = []
    for *_, nets in PARTS:
        for n in nets.values():
            if n and n not in netnames: netnames.append(n)
    codes = {n: i + 1 for i, n in enumerate(sorted(netnames))}
    fps = [bb.instantiate(r, v, lib, fp, at, rot, nets, codes)
           for r, v, lib, fp, at, rot, nets in PARTS]
    nets_sx = "\n".join(f'  (net {c} "{n}")' for n, c in sorted(codes.items(), key=lambda kv: kv[1]))
    x0, y0, x1, y1 = BOARD
    outline = (f'  (gr_rect (start {x0} {y0}) (end {x1} {y1})'
               f' (stroke (width 0.1) (type default)) (layer "Edge.Cuts") (tstamp {U()}))')
    texts = "\n".join([
        f'  (gr_text "nlink-lite" (at 57 66.8) (layer "F.SilkS") (tstamp {U()})'
        f' (effects (font (size 1 1) (thickness 0.15))))',
        f'  (gr_text "ANTENNA" (at 87 48.9) (layer "Dwgs.User") (tstamp {U()})'
        f' (effects (font (size 0.9 0.9) (thickness 0.14))))'])
    board = f"""(kicad_pcb (version 20221018) (generator nlink_gen)
  (general (thickness 1.0))
  (paper "A4")
  (layers
    (0 "F.Cu" signal) (1 "In1.Cu" signal) (2 "In2.Cu" signal) (31 "B.Cu" signal)
    (34 "B.Paste" user) (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen") (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user) (39 "F.Mask" user)
    (40 "Dwgs.User" user "User.Drawings") (44 "Edge.Cuts" user)
    (46 "B.CrtYd" user "B.Courtyard") (47 "F.CrtYd" user "F.Courtyard")
    (48 "B.Fab" user) (49 "F.Fab" user)
  )
  (setup (pad_to_mask_clearance 0))
  (net 0 "")
{nets_sx}

{outline}
{texts}

{chr(10).join(fps)}
)
"""
    out = out or os.path.join(HERE, "nlink-lite", "nlink-lite.kicad_pcb")
    open(out, "w").write(board)
    print(f"wrote {out}: {len(PARTS)} footprints, {len(netnames)} nets")

if __name__ == "__main__":
    build()
