#!/usr/bin/env python3
"""Build nlink-proto.kicad_pcb: real footprints, placed along the stick,
every pad bound to its net. Reference designators and nets match the
generated schematic exactly, so "Update PCB from Schematic" in KiCad links
cleanly instead of re-adding parts.

Layout intent seeded here (calculator end -> antenna end):
  J1 plug | ESD+CP2102N | buck | camera FPC (top) | ESP32 module (rot 90,
  antenna toward free end) | SD (flip to B.Cu in KiCad - seeded on F.Cu)
Passives sit on two rails (y=52.5 top, y=63.5 bottom) near their owners.
This is a SEED placement for hand layout, not a routed board.

Run: python3 build_board.py   then verify with verify_board.py
"""
import re, uuid, os

FPDIR = "/usr/share/kicad/footprints"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nlink-proto")

def U(): return str(uuid.uuid4())

# ---------------------------------------------------------------------------
# net map — must match generate_schematics.py (mini variant)
# ---------------------------------------------------------------------------
MINI_GND = {str(n): "GND" for n in
            [1, 2, 42, 43, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56,
             57, 58, 59, 60, 61, 62, 63, 64, 65]}
PARTS = [
    # ref, value, lib.pretty, footprint, (x, y), rot, {pad: net}
    ("J1", "USB_MiniB_PLUG_to_calc", "Connector_PinHeader_2.54mm",
     "PinHeader_1x05_P2.54mm_Vertical", (53, 52.7), 0,
     {"1": "VBUS_IN", "2": "CALC_DM", "3": "CALC_DP", "5": "GND"}),
    ("U5", "USBLC6-2SC6", "Package_TO_SOT_SMD", "SOT-23-6", (59, 53.5), 0,
     {"1": "CALC_DM", "6": "CALC_DM", "3": "CALC_DP", "4": "CALC_DP",
      "5": "VBUS", "2": "GND"}),
    ("U3", "CP2102N-A02-GQFN24", "Package_DFN_QFN",
     "QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm", (66, 58), 0,
     {"3": "CALC_DP", "4": "CALC_DM", "8": "VBUS",
      "5": "+3V3", "6": "+3V3", "7": "+3V3",
      "9": "CP_RSTn", "20": "UART_TX", "21": "UART_RX",
      "2": "GND", "25": "GND"}),
    ("SW1", "PWR_SW", "Button_Switch_SMD", "SW_SPDT_PCM12", (59, 63.5), 0,
     {"1": "VBUS", "2": "VBUS_IN"}),
    ("U4", "TLV62569DBV", "Package_TO_SOT_SMD", "SOT-23-5", (77, 58), 0,
     {"4": "VBUS", "1": "VBUS", "2": "GND", "3": "SW_NODE", "5": "FB_3V3"}),
    ("J2", "OV5640_FPC_24pin", "Connector_FFC-FPC",
     "Hirose_FH12-24S-0.5SH_1x24-1MP_P0.50mm_Horizontal", (79, 53.5), 0,
     {"1": "+3V3", "2": "GND", "3": "CAM_SIOD", "4": "CAM_SIOC",
      "5": "CAM_VSYNC", "6": "CAM_HREF", "7": "CAM_PCLK", "8": "CAM_XCLK",
      "9": "CAM_Y9", "10": "CAM_Y8", "11": "CAM_Y7", "12": "CAM_Y6",
      "13": "CAM_Y5", "14": "CAM_Y4", "15": "CAM_Y3", "16": "CAM_Y2",
      "17": "GND", "18": "+3V3", "19": "GND", "20": "GND", "MP": "GND"}),
    ("U1", "ESP32-S3-MINI-1-N4R2", "RF_Module", "ESP32-S2-MINI-1",
     (98, 58), 90,
     {"3": "+3V3", "45": "EN", "4": "IO0", "5": "STATUS_LED",
      "39": "UART_TX", "40": "UART_RX", "23": "USB_DM", "24": "USB_DP",
      "11": "SD_SCK", "12": "SD_MISO", "13": "SD_MOSI", "25": "SD_CS",
      "14": "CAM_XCLK", "36": "CAM_SIOD", "35": "CAM_SIOC",
      "19": "CAM_Y2", "21": "CAM_Y3", "22": "CAM_Y4", "20": "CAM_Y5",
      "18": "CAM_Y6", "16": "CAM_Y7", "15": "CAM_Y8", "30": "CAM_Y9",
      "34": "CAM_VSYNC", "27": "CAM_HREF", "17": "CAM_PCLK", **MINI_GND}),
    ("J3", "microSD", "Connector_Card", "microSD_HC_Hirose_DM3AT-SF-PEJM5",
     (90, 74.5), 0,   # parked in the back-side row below the outline
     {"2": "SD_CS", "3": "SD_MOSI", "4": "+3V3", "5": "SD_SCK",
      "6": "GND", "7": "SD_MISO", "9": "GND", "10": "GND", "11": "GND"}),
    ("J4", "PROG_PADS_TC2030", "Connector",
     "Tag-Connect_TC2030-IDC-FP_2x03_P1.27mm_Vertical", (86, 70), 0,
     {"1": "+3V3", "2": "GND", "3": "EN", "4": "IO0",
      "5": "USB_DM", "6": "USB_DP"}),
    ("D1", "LED_STATUS", "LED_SMD", "LED_0402_1005Metric", (90, 70), 0,
     {"1": "GND", "2": "LED_A"}),
    # passives — refs and nets in schematic call order
    ("R1", "10k", "Resistor_SMD", "R_0402_1005Metric", (70, 58), 0,
     {"1": "+3V3", "2": "CP_RSTn"}),
    ("C1", "100n", "Capacitor_SMD", "C_0402_1005Metric", (72, 58), 0,
     {"1": "+3V3", "2": "GND"}),
    ("C2", "4.7u", "Capacitor_SMD", "C_0402_1005Metric", (74, 58), 0,
     {"1": "+3V3", "2": "GND"}),
    ("L1", "2.2uH", "Inductor_SMD", "L_1210_3225Metric", (80.5, 58), 0,
     {"1": "SW_NODE", "2": "+3V3"}),
    ("R2", "453k", "Resistor_SMD", "R_0402_1005Metric", (67, 63.5), 0,
     {"1": "+3V3", "2": "FB_3V3"}),
    ("R3", "100k", "Resistor_SMD", "R_0402_1005Metric", (69, 63.5), 0,
     {"1": "FB_3V3", "2": "GND"}),
    ("C3", "10u", "Capacitor_SMD", "C_0805_2012Metric", (71.5, 63.5), 0,
     {"1": "VBUS", "2": "GND"}),
    ("C4", "22u", "Capacitor_SMD", "C_0805_2012Metric", (74, 63.5), 0,
     {"1": "+3V3", "2": "GND"}),
    ("C5", "22u", "Capacitor_SMD", "C_0805_2012Metric", (76.5, 63.5), 0,
     {"1": "+3V3", "2": "GND"}),
    ("C6", "100u", "Capacitor_SMD", "C_1210_3225Metric", (79.5, 63.5), 0,
     {"1": "+3V3", "2": "GND"}),
    ("C7", "100u", "Capacitor_SMD", "C_1210_3225Metric", (83, 63.5), 0,
     {"1": "+3V3", "2": "GND"}),
    ("R4", "4.7k", "Resistor_SMD", "R_0402_1005Metric", (93, 70), 0,
     {"1": "+3V3", "2": "CAM_SIOD"}),
    ("R5", "4.7k", "Resistor_SMD", "R_0402_1005Metric", (95, 70), 0,
     {"1": "+3V3", "2": "CAM_SIOC"}),
    ("C8", "10u", "Capacitor_SMD", "C_0805_2012Metric", (84, 58), 0,
     {"1": "+3V3", "2": "GND"}),
    ("R6", "10k", "Resistor_SMD", "R_0402_1005Metric", (97, 70), 0,
     {"1": "+3V3", "2": "SD_CS"}),
    ("R7", "10k", "Resistor_SMD", "R_0402_1005Metric", (99, 70), 0,
     {"1": "+3V3", "2": "SD_MISO"}),
    ("C9", "10u", "Capacitor_SMD", "C_0805_2012Metric", (98, 73.5), 0,
     {"1": "+3V3", "2": "GND"}),
    ("R8", "10k", "Resistor_SMD", "R_0402_1005Metric", (101, 70), 0,
     {"1": "+3V3", "2": "EN"}),
    ("C10", "100n", "Capacitor_SMD", "C_0402_1005Metric", (107, 70), 0,
     {"1": "EN", "2": "GND"}),
    ("R9", "10k", "Resistor_SMD", "R_0402_1005Metric", (103, 70), 0,
     {"1": "+3V3", "2": "IO0"}),
    ("R10", "470", "Resistor_SMD", "R_0402_1005Metric", (105, 70), 0,
     {"1": "STATUS_LED", "2": "LED_A"}),
    ("C11", "100n", "Capacitor_SMD", "C_0402_1005Metric", (100.5, 73.5), 0,
     {"1": "+3V3", "2": "GND"}),
    ("C12", "10u", "Capacitor_SMD", "C_0805_2012Metric", (103, 73.5), 0,
     {"1": "+3V3", "2": "GND"}),
]

# ---------------------------------------------------------------------------
# footprint munging
# ---------------------------------------------------------------------------
def balanced(text, start):
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '(': depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0: return i + 1
    raise ValueError("unbalanced")

def load_footprint(lib, name):
    return open(f"{FPDIR}/{lib}.pretty/{name}.kicad_mod").read()

PAD_RE = re.compile(r'\(pad\s+("?)([^\s"]*)\1\s')

def instantiate(ref, value, lib, name, at, rot, nets, netcodes):
    raw = load_footprint(lib, name)
    # root rename + strip version/generator, add placement + tstamp
    raw = re.sub(r'^\(footprint\s+"?' + re.escape(name) + r'"?',
                 f'(footprint "{lib}:{name}"', raw)
    raw = re.sub(r'\(version\s+\d+\)\s*', '', raw, count=1)
    raw = re.sub(r'\(generator\s+\S+\)\s*', '', raw, count=1)
    # both quoted and unquoted layer forms exist across library vintages
    raw = re.sub(r'\(layer "?F\.Cu"?\)',
                 f'(layer "F.Cu")\n  (tstamp {U()})\n'
                 f'  (at {at[0]} {at[1]} {rot})', raw, count=1)
    # reference / value texts (quoted or bare tokens)
    raw = re.sub(r'\(fp_text reference (?:"[^"]*"|\S+)',
                 f'(fp_text reference "{ref}"', raw, count=1)
    raw = re.sub(r'\(fp_text value (?:"[^"]*"|\S+)',
                 f'(fp_text value "{value}"', raw, count=1)

    # walk pads: add net, apply footprint rotation to pad angles
    out, pos = [], 0
    for m in PAD_RE.finditer(raw):
        padname = m.group(2)
        end = balanced(raw, m.start())
        block = raw[m.start():end]
        if rot:
            def bump(mm):
                parts = mm.group(1).split()
                x, y = parts[0], parts[1]
                a = float(parts[2]) if len(parts) > 2 else 0.0
                return f'(at {x} {y} {(a + rot) % 360:g})'
            block = re.sub(r'\(at ([^)]*)\)', bump, block, count=1)
        net = nets.get(padname)
        if net:
            code = netcodes[net]
            block = block[:-1].rstrip() + f' (net {code} "{net}"))'
        out.append(raw[pos:m.start()] + block)
        pos = end
    out.append(raw[pos:])
    body = "".join(out)
    # add missing tedit tolerance: none needed for v7
    return "  " + body.replace("\n", "\n  ")

# ---------------------------------------------------------------------------
def build():
    # net table
    netnames = []
    for *_, nets in PARTS:
        for n in nets.values():
            if n and n not in netnames:
                netnames.append(n)
    netcodes = {n: i + 1 for i, n in enumerate(sorted(netnames))}

    fps = [instantiate(ref, val, lib, name, at, rot, nets, netcodes)
           for ref, val, lib, name, at, rot, nets in PARTS]

    nets_sexpr = "\n".join(f'  (net {c} "{n}")'
                           for n, c in sorted(netcodes.items(), key=lambda kv: kv[1]))
    outline = (f'  (gr_rect (start 50 50) (end 110 66)'
               f' (stroke (width 0.1) (type default)) (layer "Edge.Cuts")'
               f' (tstamp {U()}))')
    notes = [
        ("BACK-SIDE SET: flip these (F) and tuck under the module", 78, 68.2),
        ("antenna end ->", 106, 48.5),
        ("nlink-proto 60x16  (placement seed, unrouted)", 55, 48.5),
    ]
    texts = "\n".join(
        f'  (gr_text "{t}" (at {x} {y}) (layer "Dwgs.User") (tstamp {U()})'
        f' (effects (font (size 1 1) (thickness 0.15))))' for t, x, y in notes)

    board = f"""(kicad_pcb (version 20221018) (generator nlink_gen)
  (general (thickness 1.0))
  (paper "A4")
  (layers
    (0 "F.Cu" signal) (1 "In1.Cu" signal) (2 "In2.Cu" signal)
    (31 "B.Cu" signal)
    (32 "B.Adhes" user "B.Adhesive") (33 "F.Adhes" user "F.Adhesive")
    (34 "B.Paste" user) (35 "F.Paste" user)
    (36 "B.SilkS" user "B.Silkscreen") (37 "F.SilkS" user "F.Silkscreen")
    (38 "B.Mask" user) (39 "F.Mask" user)
    (40 "Dwgs.User" user "User.Drawings") (41 "Cmts.User" user "User.Comments")
    (44 "Edge.Cuts" user) (46 "B.CrtYd" user "B.Courtyard")
    (47 "F.CrtYd" user "F.Courtyard") (48 "B.Fab" user) (49 "F.Fab" user)
  )
  (setup (pad_to_mask_clearance 0))
  (net 0 "")
{nets_sexpr}

{outline}
{texts}

{chr(10).join(fps)}
)
"""
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "nlink-proto.kicad_pcb")
    open(path, "w").write(board)
    print(f"wrote {path}: {len(PARTS)} footprints, {len(netnames)} nets")

if __name__ == "__main__":
    build()
