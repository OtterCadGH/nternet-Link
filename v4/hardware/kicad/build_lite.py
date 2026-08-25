#!/usr/bin/env python3
"""Build nlink-lite.kicad_pcb — tiny chat-only stealth board (34x15mm).
Reuses build_board.instantiate(); footprints load from stock libs + project lib.
Placement seed only, unrouted. Refs/nets match nlink-lite schematic.
Run: python3 build_lite.py  → verify with verify_board.py-style check inline.
"""
import os, uuid, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("bb", os.path.join(HERE, "build_board.py"))
bb = importlib.util.module_from_spec(spec); spec.loader.exec_module(bb)

# footprint search: stock dir + vendored Espressif.pretty
FP_DIRS = ["/usr/share/kicad/footprints", os.path.join(HERE, "lib")]
def load_fp(lib, name):
    for d in FP_DIRS:
        p = f"{d}/{lib}.pretty/{name}.kicad_mod"
        if os.path.exists(p): return open(p).read()
    raise FileNotFoundError(f"{lib}:{name}")
bb.load_footprint = load_fp   # monkeypatch so instantiate() finds vendored FPs

def U(): return str(uuid.uuid4())

# C3-MINI-1: main GNDs + signal pads (pad numbers from Espressif footprint)
C3_GND = {str(n): "GND" for n in
          [1, 2, 11, 14, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48,
           49, 50, 51, 52, 53]}
PARTS = [
    ("J1", "USB_MiniB_PLUG_to_calc", "Connector_PinHeader_2.54mm",
     "PinHeader_1x05_P2.54mm_Vertical", (55, 58), 0,
     {"1": "VBUS_IN", "2": "CALC_DM", "3": "CALC_DP", "5": "GND"}),
    ("U5", "USBLC6-2SC6", "Package_TO_SOT_SMD", "SOT-23-6", (60, 54), 0,
     {"1": "CALC_DM", "6": "CALC_DM", "3": "CALC_DP", "4": "CALC_DP",
      "5": "VBUS", "2": "GND"}),
    ("U3", "CP2102N-A02-GQFN24", "Package_DFN_QFN",
     "QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm", (66, 58), 0,
     {"3": "CALC_DP", "4": "CALC_DM", "8": "VBUS", "5": "+3V3", "6": "+3V3",
      "7": "+3V3", "9": "CP_RSTn", "20": "UART_TX", "21": "UART_RX",
      "2": "GND", "25": "GND"}),
    ("SW1", "PWR_SW", "Button_Switch_SMD", "SW_SPDT_PCM12", (60, 62), 0,
     {"1": "VBUS", "2": "VBUS_IN"}),
    ("U4", "TLV62569DBV", "Package_TO_SOT_SMD", "SOT-23-5", (72, 62), 0,
     {"4": "VBUS", "1": "VBUS", "2": "GND", "3": "SW_NODE", "5": "FB_3V3"}),
    ("U1", "ESP32-C3-MINI-1-N4", "Espressif", "ESP32-C3-MINI-1", (79, 58), 0,
     {"3": "+3V3", "8": "EN", "12": "IO0", "22": "STATUS_LED",
      "21": "UART_TX", "20": "UART_RX", "26": "USB_DM", "27": "USB_DP",
      **C3_GND}),
    ("J4", "PROG_PADS_TC2030", "Connector",
     "Tag-Connect_TC2030-IDC-FP_2x03_P1.27mm_Vertical", (72, 66), 0,
     {"1": "+3V3", "2": "GND", "3": "EN", "4": "IO0", "5": "USB_DM", "6": "USB_DP"}),
    ("D1", "LED_STATUS", "LED_SMD", "LED_0402_1005Metric", (77, 66), 0,
     {"1": "GND", "2": "LED_A"}),
    ("R1", "10k", "Resistor_SMD", "R_0402_1005Metric", (69, 54), 0, {"1": "+3V3", "2": "CP_RSTn"}),
    ("C1", "100n", "Capacitor_SMD", "C_0402_1005Metric", (71, 54), 0, {"1": "+3V3", "2": "GND"}),
    ("C2", "4.7u", "Capacitor_SMD", "C_0402_1005Metric", (73, 54), 0, {"1": "+3V3", "2": "GND"}),
    ("L1", "2.2uH", "Inductor_SMD", "L_1210_3225Metric", (76, 62), 0, {"1": "SW_NODE", "2": "+3V3"}),
    ("R2", "453k", "Resistor_SMD", "R_0402_1005Metric", (66, 66), 0, {"1": "+3V3", "2": "FB_3V3"}),
    ("R3", "100k", "Resistor_SMD", "R_0402_1005Metric", (68, 66), 0, {"1": "FB_3V3", "2": "GND"}),
    ("C3", "10u", "Capacitor_SMD", "C_0805_2012Metric", (63, 66), 0, {"1": "VBUS", "2": "GND"}),
    ("C4", "22u", "Capacitor_SMD", "C_0805_2012Metric", (85, 54), 0, {"1": "+3V3", "2": "GND"}),
    ("C5", "10u", "Capacitor_SMD", "C_0805_2012Metric", (85, 62), 0, {"1": "+3V3", "2": "GND"}),
    ("R4", "10k", "Resistor_SMD", "R_0402_1005Metric", (82, 66), 0, {"1": "+3V3", "2": "EN"}),
    ("C6", "100n", "Capacitor_SMD", "C_0402_1005Metric", (84, 66), 0, {"1": "EN", "2": "GND"}),
    ("R5", "10k", "Resistor_SMD", "R_0402_1005Metric", (86, 66), 0, {"1": "+3V3", "2": "IO0"}),
    ("R6", "470", "Resistor_SMD", "R_0402_1005Metric", (79, 66), 0, {"1": "STATUS_LED", "2": "LED_A"}),
]

def build():
    netnames = []
    for *_, nets in PARTS:
        for n in nets.values():
            if n and n not in netnames: netnames.append(n)
    codes = {n: i + 1 for i, n in enumerate(sorted(netnames))}
    fps = [bb.instantiate(r, v, lib, fp, at, rot, nets, codes)
           for r, v, lib, fp, at, rot, nets in PARTS]
    nets_sx = "\n".join(f'  (net {c} "{n}")' for n, c in sorted(codes.items(), key=lambda kv: kv[1]))
    outline = (f'  (gr_rect (start 50 50) (end 89 66) (stroke (width 0.1) (type default))'
               f' (layer "Edge.Cuts") (tstamp {U()}))')
    note = (f'  (gr_text "nlink-lite ~38x16  chat-only stealth  (placement seed, unrouted)"'
            f' (at 67 48.5) (layer "Dwgs.User") (tstamp {U()})'
            f' (effects (font (size 1 1) (thickness 0.15))))')
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
{note}

{chr(10).join(fps)}
)
"""
    out = os.path.join(HERE, "nlink-lite", "nlink-lite.kicad_pcb")
    open(out, "w").write(board)
    print(f"wrote {out}: {len(PARTS)} footprints, {len(netnames)} nets")

if __name__ == "__main__":
    build()
