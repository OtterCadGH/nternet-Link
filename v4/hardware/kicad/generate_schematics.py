#!/usr/bin/env python3
"""Generate nlink-proto and nlink-stick KiCad schematics + board stubs.

Reads official KiCad 7 symbol libraries, places symbols in a utilitarian grid,
and attaches global labels at exact pin coordinates (label-everything style —
connectivity lives in the labels, no drawn wires). Verified afterwards by
exporting the netlist with kicad-cli and asserting the nets from
CAPTURE-PLAN.md — see verify_netlists.py.

Regenerate: python3 generate_schematics.py
"""
import re, uuid, os, json

OUT = os.path.dirname(os.path.abspath(__file__))
# Stock KiCad symbols + the project's vendored Espressif library (C3-MINI-1).
LIBDIRS = ["/usr/share/kicad/symbols", os.path.join(OUT, "lib")]

# ---------------------------------------------------------------------------
# symbol library access
# ---------------------------------------------------------------------------
def extract_symbol_text(lib, name):
    """Return the raw s-expr text of (symbol "name" ...) from a library."""
    text = None
    for d in LIBDIRS:
        p = f"{d}/{lib}.kicad_sym"
        if os.path.exists(p) and f'(symbol "{name}"' in open(p).read():
            text = open(p).read()
            break
    if text is None:
        raise FileNotFoundError(f"symbol {lib}:{name} not found in {LIBDIRS}")
    marker = f'(symbol "{name}"'
    start = text.index(marker)
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '(':
            depth += 1
        elif text[i] == ')':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    raise ValueError(name)

def parse_pins(sym_text):
    """[(number, name, x, y, angle)] from a symbol's raw text."""
    pins = []
    for m in re.finditer(
        r'\(pin\s+\S+\s+\S+\s*\(at\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\)'
        r'.*?\(name\s+"([^"]*)".*?\(number\s+"([^"]*)"', sym_text, re.S):
        x, y, ang, name, num = m.groups()
        pins.append((num, name, float(x), float(y), float(ang)))
    return pins

def U(): return str(uuid.uuid4())
def fmt(v): return f"{round(v + 0.0, 2):g}"

# ---------------------------------------------------------------------------
# schematic writer
# ---------------------------------------------------------------------------
class Schematic:
    def __init__(self, project):
        self.project = project
        self.root_uuid = U()
        self.libparts = {}     # "Lib:Name" -> embedded text
        self.body = []

    def use_symbol(self, lib, name):
        key = f"{lib}:{name}"
        if key not in self.libparts:
            raw = extract_symbol_text(lib, name)
            raw = raw.replace(f'(symbol "{name}"', f'(symbol "{key}"', 1)
            self.libparts[key] = raw
        return key

    def place(self, ref, lib, name, value, footprint, at, nets, extra_props=None):
        """Place symbol at `at`; nets maps pin_number -> net label (None=NC)."""
        key = self.use_symbol(lib, name)
        pins = parse_pins(self.libparts[key])
        sx, sy = at
        su = U()
        p = [f'  (symbol (lib_id "{key}") (at {fmt(sx)} {fmt(sy)} 0) (unit 1)',
             f'    (in_bom yes) (on_board yes) (dnp no) (uuid {su})',
             f'    (property "Reference" "{ref}" (at {fmt(sx)} {fmt(sy - 2.54)} 0)',
             f'      (effects (font (size 1.27 1.27))))',
             f'    (property "Value" "{value}" (at {fmt(sx)} {fmt(sy)} 0)',
             f'      (effects (font (size 1.27 1.27))))',
             f'    (property "Footprint" "{footprint}" (at {fmt(sx)} {fmt(sy)} 0)',
             f'      (effects (font (size 1.27 1.27)) hide))',
             f'    (property "Datasheet" "" (at {fmt(sx)} {fmt(sy)} 0)',
             f'      (effects (font (size 1.27 1.27)) hide))']
        for k, v in (extra_props or {}).items():
            p.append(f'    (property "{k}" "{v}" (at {fmt(sx)} {fmt(sy)} 0)'
                     f' (effects (font (size 1.27 1.27)) hide))')
        for num, _, _, _, _ in pins:
            p.append(f'    (pin "{num}" (uuid {U()}))')
        p.append(f'    (instances (project "{self.project}"'
                 f' (path "/{self.root_uuid}" (reference "{ref}") (unit 1))))')
        p.append('  )')
        self.body.append("\n".join(p))

        # labels / no-connects at pin endpoints, grouped by position
        by_pos = {}
        for num, pname, px, py, pang in pins:
            pos = (round(sx + px, 2), round(sy - py, 2))
            by_pos.setdefault(pos, []).append((num, pname, pang))
        for (x, y), plist in by_pos.items():
            netnames = {nets.get(num) for num, _, _ in plist if nets.get(num)}
            assert len(netnames) <= 1, f"{ref}: conflicting nets at {(x,y)}: {netnames}"
            if netnames:
                net = netnames.pop()
                ang = plist[0][2]
                lang = {0: 180, 180: 0, 90: 270, 270: 90}.get(ang, 0)
                just = "right" if lang == 180 else "left"
                self.body.append(
                    f'  (global_label "{net}" (shape passive)'
                    f' (at {fmt(x)} {fmt(y)} {lang})'
                    f' (effects (font (size 1.27 1.27)) (justify {just}))'
                    f' (uuid {U()}))')
            else:
                self.body.append(f'  (no_connect (at {fmt(x)} {fmt(y)}) (uuid {U()}))')

    def text(self, s, at, size=2.0):
        x, y = at
        s = s.replace('"', "'")
        self.body.append(
            f'  (text "{s}" (at {fmt(x)} {fmt(y)} 0)'
            f' (effects (font (size {size} {size}) bold) (justify left bottom))'
            f' (uuid {U()}))')

    def write(self, path):
        out = ['(kicad_sch (version 20230121) (generator nlink_gen)', '',
               f'  (uuid {self.root_uuid})', '', '  (paper "A2")', '',
               '  (lib_symbols']
        for raw in self.libparts.values():
            out.append("    " + raw.replace("\n", "\n    "))
        out.append('  )')
        out.append('')
        out.extend(self.body)
        out.append('')
        out.append(f'  (sheet_instances (path "/" (page "1")))')
        out.append(')')
        open(path, "w").write("\n".join(out) + "\n")

# ---------------------------------------------------------------------------
# passive helper
# ---------------------------------------------------------------------------
class Ctx:
    def __init__(self, sch):
        self.sch = sch
        self.n = {"R": 0, "C": 0, "L": 0}
    def rcl(self, kind, value, at, net1, net2, fp=None):
        self.n[kind] += 1
        ref = f"{kind}{self.n[kind]}"
        fp = fp or {"R": "Resistor_SMD:R_0402_1005Metric",
                    "C": "Capacitor_SMD:C_0402_1005Metric",
                    "L": "Inductor_SMD:L_1210_3225Metric"}[kind]
        self.sch.place(ref, "Device", kind, value, fp, at, {"1": net1, "2": net2})
        return ref

# ---------------------------------------------------------------------------
# shared circuitry (both variants)
# ---------------------------------------------------------------------------
def add_shared(sch, ctx):
    # --- calculator plug + ESD + bridge --------------------------------------
    sch.text("USB BRIDGE — calc mini-B plug, ESD, CP2102N", (30, 22), 1.7)
    sch.place("J1", "Connector_Generic", "Conn_01x05", "USB_MiniB_PLUG_to_calc",
              "", (40, 40),
              {"1": "VBUS_IN", "2": "CALC_DM", "3": "CALC_DP", "5": "GND"},
              {"MPN": "mini-B male plug — see PCB-DESIGN.md options"})
    sch.place("U5", "Power_Protection", "USBLC6-2P6", "USBLC6-2SC6",
              "Package_TO_SOT_SMD:SOT-23-6", (70, 40),
              {"1": "CALC_DM", "6": "CALC_DM", "3": "CALC_DP", "4": "CALC_DP",
               "5": "VBUS", "2": "GND"})
    sch.place("U3", "Interface_USB", "CP2102N-Axx-xQFN24", "CP2102N-A02-GQFN24",
              "Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm", (110, 45),
              {"3": "CALC_DP", "4": "CALC_DM", "8": "VBUS",
               "5": "+3V3", "6": "+3V3", "7": "+3V3",
               "9": "CP_RSTn", "20": "UART_TX", "21": "UART_RX",
               "2": "GND", "25": "GND"})
    ctx.rcl("R", "10k", (140, 30), "+3V3", "CP_RSTn")
    ctx.rcl("C", "100n", (150, 30), "+3V3", "GND")
    ctx.rcl("C", "4.7u", (160, 30), "+3V3", "GND")

    # --- power ---------------------------------------------------------------
    sch.text("POWER — VBUS switch + 3V3 buck", (30, 82), 1.7)
    sch.place("SW1", "Switch", "SW_SPDT", "PWR_SW", "", (40, 95),
              {"2": "VBUS_IN", "1": "VBUS"})
    sch.place("U4", "Regulator_Switching", "TLV62568DBV", "TLV62569DBV",
              "Package_TO_SOT_SMD:SOT-23-5", (70, 95),
              {"4": "VBUS", "1": "VBUS", "2": "GND", "3": "SW_NODE", "5": "FB_3V3"})
    ctx.rcl("L", "2.2uH", (90, 88), "SW_NODE", "+3V3")
    ctx.rcl("R", "453k", (100, 88), "+3V3", "FB_3V3")
    ctx.rcl("R", "100k", (108, 88), "FB_3V3", "GND")
    ctx.rcl("C", "10u", (116, 88), "VBUS", "GND",
            fp="Capacitor_SMD:C_0805_2012Metric")
    ctx.rcl("C", "22u", (124, 88), "+3V3", "GND",
            fp="Capacitor_SMD:C_0805_2012Metric")
    ctx.rcl("C", "22u", (132, 88), "+3V3", "GND",
            fp="Capacitor_SMD:C_0805_2012Metric")
    ctx.rcl("C", "100u", (140, 88), "+3V3", "GND",
            fp="Capacitor_SMD:C_1210_3225Metric")
    ctx.rcl("C", "100u", (148, 88), "+3V3", "GND",
            fp="Capacitor_SMD:C_1210_3225Metric")

def add_camera_sd(sch, ctx):
    # --- camera --------------------------------------------------------------
    sch.text("CAMERA — OV5640 24-pin FPC", (30, 128), 1.7)
    sch.text("!! pin order = PLACEHOLDER — remap to your", (30, 132), 1.7)
    sch.text("module's FPC pinout before layout !!", (30, 136), 1.7)
    cam = {"1": "+3V3", "2": "GND", "3": "CAM_SIOD", "4": "CAM_SIOC",
           "5": "CAM_VSYNC", "6": "CAM_HREF", "7": "CAM_PCLK", "8": "CAM_XCLK",
           "9": "CAM_Y9", "10": "CAM_Y8", "11": "CAM_Y7", "12": "CAM_Y6",
           "13": "CAM_Y5", "14": "CAM_Y4", "15": "CAM_Y3", "16": "CAM_Y2",
           "17": "GND", "18": "+3V3", "19": "GND", "20": "GND"}
    sch.place("J2", "Connector_Generic", "Conn_01x24", "OV5640_FPC_24pin",
              "Connector_FFC-FPC:Hirose_FH12-24S-0.5SH_1x24-1MP_P0.50mm_Horizontal",
              (45, 175), cam)
    ctx.rcl("R", "4.7k", (70, 150), "+3V3", "CAM_SIOD")
    ctx.rcl("R", "4.7k", (78, 150), "+3V3", "CAM_SIOC")
    ctx.rcl("C", "10u", (86, 150), "+3V3", "GND",
            fp="Capacitor_SMD:C_0805_2012Metric")

    # --- microSD -------------------------------------------------------------
    sch.text("microSD — SPI mode, <=12.5mm socket on stick", (130, 128), 1.7)
    sch.place("J3", "Connector", "Micro_SD_Card", "microSD",
              "Connector_Card:microSD_HC_Hirose_DM3AT-SF-PEJM5", (150, 160),
              {"2": "SD_CS", "3": "SD_MOSI", "4": "+3V3", "5": "SD_SCK",
               "6": "GND", "7": "SD_MISO", "9": "GND"})
    ctx.rcl("R", "10k", (180, 145), "+3V3", "SD_CS")
    ctx.rcl("R", "10k", (188, 145), "+3V3", "SD_MISO")
    ctx.rcl("C", "10u", (196, 145), "+3V3", "GND",
            fp="Capacitor_SMD:C_0805_2012Metric")

def add_program(sch, ctx):
    # --- programming pads + straps + LED -------------------------------------
    sch.text("PROGRAM — TC2030/pogo: USB + straps (IO0 low at boot = flash)", (130, 82), 1.7)
    sch.place("J4", "Connector_Generic", "Conn_01x06", "PROG_PADS_TC2030",
              "Connector:Tag-Connect_TC2030-IDC-FP_2x03_P1.27mm_Vertical",
              (150, 100),
              {"1": "+3V3", "2": "GND", "3": "EN", "4": "IO0",
               "5": "USB_DM", "6": "USB_DP"})
    ctx.rcl("R", "10k", (175, 92), "+3V3", "EN")
    ctx.rcl("C", "100n", (183, 92), "EN", "GND")
    ctx.rcl("R", "10k", (191, 92), "+3V3", "IO0")
    ctx.rcl("R", "470", (199, 92), "STATUS_LED", "LED_A")
    sch.place("D1", "Device", "LED", "LED_STATUS",
              "LED_SMD:LED_0402_1005Metric", (207, 100),
              {"2": "LED_A", "1": "GND"})

# ---------------------------------------------------------------------------
# variant MCU sections
# ---------------------------------------------------------------------------
def add_mcu_mini(sch, ctx):
    sch.text("MCU — ESP32-S3-MINI-1-N4R2 (R2 required: PSRAM)", (235, 22), 1.7)
    sch.place("U1", "MCU_Espressif", "ESP32-S3-MINI-1", "ESP32-S3-MINI-1-N4R2",
              "RF_Module:ESP32-S3-MINI-1", (270, 70),
              {"3": "+3V3", "45": "EN", "4": "IO0", "5": "STATUS_LED",
               "39": "UART_TX", "40": "UART_RX",
               "23": "USB_DM", "24": "USB_DP",
               "11": "SD_SCK", "12": "SD_MISO", "13": "SD_MOSI", "25": "SD_CS",
               "14": "CAM_XCLK", "36": "CAM_SIOD", "35": "CAM_SIOC",
               "19": "CAM_Y2", "21": "CAM_Y3", "22": "CAM_Y4", "20": "CAM_Y5",
               "18": "CAM_Y6", "16": "CAM_Y7", "15": "CAM_Y8", "30": "CAM_Y9",
               "34": "CAM_VSYNC", "27": "CAM_HREF", "17": "CAM_PCLK",
               **{str(n): "GND" for n in
                  [1, 2, 42, 43, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56,
                   57, 58, 59, 60, 61, 62, 63, 64, 65]}})
    ctx.rcl("C", "100n", (296, 40), "+3V3", "GND")
    ctx.rcl("C", "10u", (304, 40), "+3V3", "GND",
            fp="Capacitor_SMD:C_0805_2012Metric")

def add_mcu_bare(sch, ctx):
    sch.text("MCU — bare ESP32-S3R8 + flash + xtal + RF", (235, 22), 1.7)
    sch.place("U1", "MCU_Espressif", "ESP32-S3", "ESP32-S3R8",
              "Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm_EP4.15x4.15mm",
              (270, 75),
              {"1": "RF_FEED", "4": "EN",
               "2": "+3V3", "3": "+3V3", "20": "+3V3", "46": "+3V3",
               "55": "+3V3", "56": "+3V3", "29": "VDD_SPI", "57": "GND",
               "5": "IO0", "6": "STATUS_LED",
               "49": "UART_TX", "50": "UART_RX",
               "25": "USB_DM", "26": "USB_DP",
               "12": "SD_SCK", "13": "SD_MISO", "14": "SD_MOSI", "27": "SD_CS",
               "15": "CAM_XCLK", "45": "CAM_SIOD", "44": "CAM_SIOC",
               "21": "CAM_Y2", "23": "CAM_Y3", "24": "CAM_Y4", "22": "CAM_Y5",
               "19": "CAM_Y6", "17": "CAM_Y7", "16": "CAM_Y8", "36": "CAM_Y9",
               "43": "CAM_VSYNC", "37": "CAM_HREF", "18": "CAM_PCLK",
               "30": "FLASH_HD", "31": "FLASH_WP", "32": "FLASH_CS",
               "33": "FLASH_CLK", "34": "FLASH_Q", "35": "FLASH_D",
               "53": "XTAL_N", "54": "XTAL_P"})
    sch.place("U2", "Memory_Flash", "W25Q32JVSS", "W25Q64JVSSIQ",
              "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", (320, 45),
              {"1": "FLASH_CS", "6": "FLASH_CLK", "5": "FLASH_D",
               "2": "FLASH_Q", "3": "FLASH_WP", "7": "FLASH_HD",
               "8": "VDD_SPI", "4": "GND"})
    ctx.rcl("C", "1u", (338, 38), "VDD_SPI", "GND")
    sch.place("Y1", "Device", "Crystal_GND24", "40MHz",
              "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm", (320, 80),
              {"1": "XTAL_P", "3": "XTAL_N", "2": "GND", "4": "GND"})
    ctx.rcl("C", "12p", (332, 74), "XTAL_P", "GND")
    ctx.rcl("C", "12p", (340, 74), "XTAL_N", "GND")
    # RF pi match + antenna
    sch.text("RF: 50R trace, pi-match, antenna keepout", (300, 105), 1.7)
    ctx.rcl("C", "DNP", (310, 115), "RF_FEED", "GND")
    ctx.rcl("L", "0R-placeholder", (318, 115), "RF_FEED", "ANT_FEED",
            fp="Inductor_SMD:L_0402_1005Metric")
    ctx.rcl("C", "DNP", (326, 115), "ANT_FEED", "GND")
    sch.place("ANT1", "Device", "Antenna_Chip", "2450AT18B100",
              "RF_Antenna:Johanson_2450AT18x100", (340, 115),
              {"1": "ANT_FEED"})
    # decoupling farm
    for i, v in enumerate(["100n", "100n", "100n", "1u", "10u"]):
        ctx.rcl("C", v, (250 + i * 12, 122), "+3V3", "GND",
                fp="Capacitor_SMD:C_0805_2012Metric" if v == "10u" else None)

def add_mcu_pico(sch, ctx):
    # ESP32-S3-PICO-1 SiP: same S3 die, but flash + PSRAM + 40MHz crystal are
    # bonded INSIDE the package, so the SPI-flash pads (30-35) and XTAL pads
    # (53,54) are NC externally. Reuse the bare-S3 symbol; drop the external
    # flash chip and crystal that add_mcu_bare needed. Pin numbers are 1:1 with
    # the PICO-1 LGA-56 pad map (datasheet v1.2). Antenna is still external.
    sch.text("MCU — ESP32-S3-PICO-1 SiP (flash+PSRAM+xtal in-package)",
             (235, 22), 1.7)
    sch.text("footprint: add Espressif LGA-56 land pattern before layout",
             (235, 26), 1.5)
    sch.place("U1", "MCU_Espressif", "ESP32-S3", "ESP32-S3-PICO-1-N8R8",
              "Espressif:ESP32-S3-PICO-1",  # add land pattern in KiCad
              (270, 75),
              {"1": "RF_FEED", "4": "EN",
               "2": "+3V3", "3": "+3V3", "20": "+3V3", "46": "+3V3",
               "55": "+3V3", "56": "+3V3", "29": "VDD_SPI", "57": "GND",
               "5": "IO0", "6": "STATUS_LED",
               "49": "UART_TX", "50": "UART_RX",
               "25": "USB_DM", "26": "USB_DP",
               "12": "SD_SCK", "13": "SD_MISO", "14": "SD_MOSI", "27": "SD_CS",
               "15": "CAM_XCLK", "45": "CAM_SIOD", "44": "CAM_SIOC",
               "21": "CAM_Y2", "23": "CAM_Y3", "24": "CAM_Y4", "22": "CAM_Y5",
               "19": "CAM_Y6", "17": "CAM_Y7", "16": "CAM_Y8", "36": "CAM_Y9",
               "43": "CAM_VSYNC", "37": "CAM_HREF", "18": "CAM_PCLK"})
    # pads 30-35 (int. flash), 53-54 (int. xtal) intentionally left NC
    ctx.rcl("C", "1u", (300, 40), "VDD_SPI", "GND")
    # RF pi match + antenna (external, same as bare)
    sch.text("RF: 50R trace, pi-match, antenna keepout", (300, 105), 1.7)
    ctx.rcl("C", "DNP", (310, 115), "RF_FEED", "GND")
    ctx.rcl("L", "0R-placeholder", (318, 115), "RF_FEED", "ANT_FEED",
            fp="Inductor_SMD:L_0402_1005Metric")
    ctx.rcl("C", "DNP", (326, 115), "ANT_FEED", "GND")
    sch.place("ANT1", "Device", "Antenna_Chip", "2450AT18B100",
              "RF_Antenna:Johanson_2450AT18x100", (340, 115),
              {"1": "ANT_FEED"})
    for i, v in enumerate(["100n", "100n", "1u", "10u"]):
        ctx.rcl("C", v, (250 + i * 12, 122), "+3V3", "GND",
                fp="Capacitor_SMD:C_0805_2012Metric" if v == "10u" else None)

def add_mcu_c3(sch, ctx):
    # ESP32-C3-MINI-1: pre-certified module — PCB antenna + 4MB flash inside.
    # No external RF, flash, crystal, PSRAM. Chat-only lite board.
    sch.text("MCU — ESP32-C3-MINI-1 (module: antenna+flash integrated)",
             (235, 22), 1.7)
    c3gnd = {str(n): "GND" for n in
             [1, 2, 11, 14, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47,
              48, 49, 50, 51, 52, 53]}
    sch.place("U1", "nlink_parts", "ESP32-C3-MINI-1", "ESP32-C3-MINI-1-N4",
              "Espressif:ESP32-C3-MINI-1", (270, 70),
              {"3": "+3V3", "8": "EN", "12": "IO0", "22": "STATUS_LED",
               "21": "UART_TX", "20": "UART_RX",   # GPIO7 tx, GPIO6 rx
               "26": "USB_DM", "27": "USB_DP",      # GPIO18/19 native USB
               **c3gnd})
    ctx.rcl("C", "100n", (300, 40), "+3V3", "GND")
    ctx.rcl("C", "10u", (308, 40), "+3V3", "GND",
            fp="Capacitor_SMD:C_0805_2012Metric")

# ---------------------------------------------------------------------------
# board stub with outline
# ---------------------------------------------------------------------------
def write_pcb(path, w, h):
    open(path, "w").write(f"""(kicad_pcb (version 20221018) (generator nlink_gen)
  (general (thickness 1.0))
  (paper "A4")
  (layers
    (0 "F.Cu" signal) (1 "In1.Cu" signal) (2 "In2.Cu" signal)
    (31 "B.Cu" signal) (36 "B.SilkS" user) (37 "F.SilkS" user)
    (38 "B.Mask" user) (39 "F.Mask" user)
    (44 "Edge.Cuts" user) (40 "Dwgs.User" user)
  )
  (setup (pad_to_mask_clearance 0))
  (gr_rect (start 50 50) (end {50 + w} {50 + h})
    (stroke (width 0.1) (type default)) (layer "Edge.Cuts") (tstamp {U()}))
  (gr_text "nternet-Link {w}x{h}mm outline" (at {50 + w / 2} {48}) (layer "Dwgs.User")
    (tstamp {U()}) (effects (font (size 1.5 1.5) (thickness 0.3))))
)
""")

def write_pro(path, name):
    json.dump({"meta": {"filename": f"{name}.kicad_pro", "version": 1},
               "boards": [], "libraries": {"pinned_footprint_libs": [],
               "pinned_symbol_libs": []}, "sheets": []},
              open(path, "w"), indent=2)

# ---------------------------------------------------------------------------
# name, title, mcu-fn, has camera+sd?, board (w,h)
MODELS = {
    "mini": ("nlink-proto", "ESP32-S3-MINI-1 prototype (~60x16mm)",
             "add_mcu_mini", True, (60, 16)),
    "bare": ("nlink-stick", "bare ESP32-S3R8 stick (<=60x12.5mm)",
             "add_mcu_bare", True, (60, 12.5)),
    "cam":  ("nlink-cam", "ESP32-S3-PICO-1 camera stick (<=60x12.5mm)",
             "add_mcu_pico", True, (60, 12.5)),
    "lite": ("nlink-lite", "ESP32-C3-MINI-1 chat-only stealth",
             "add_mcu_c3", False, (34, 15)),
}

def build(variant):
    name, title, mcu_fn, full, board = MODELS[variant]
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    sch = Schematic(name)
    ctx = Ctx(sch)
    sch.text(f"nternet-Link V4 · {name} — {title} · generated, netlist-verified"
             " — tidy placement freely, nets live in the labels", (30, 12), 2.5)
    add_shared(sch, ctx)            # calc plug + ESD + bridge + 3V3 buck
    if full:
        add_camera_sd(sch, ctx)     # OV5640 FPC + microSD
    add_program(sch, ctx)           # TC2030 pads + straps + LED
    globals()[mcu_fn](sch, ctx)     # MCU section
    sch.write(os.path.join(d, f"{name}.kicad_sch"))
    write_pro(os.path.join(d, f"{name}.kicad_pro"), name)
    write_pcb(os.path.join(d, f"{name}.kicad_pcb"), *board)
    print(f"wrote {name}")

if __name__ == "__main__":
    for v in MODELS:
        build(v)
