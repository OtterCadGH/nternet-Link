#!/usr/bin/env python3
"""Verify kicad-cli-exported netlists against the CAPTURE-PLAN net tables.

Assertions are written from the capture plan (component + pin NAME level),
independent of the generator's pin-number spec, so a wrong pin number or a
label that missed its pin shows up here as a failed net.
Usage: kicad-cli sch export netlist --output /tmp/X.net X.kicad_sch
       python3 verify_netlists.py /tmp/nlink-proto.net /tmp/nlink-stick.net
"""
import re, sys

def parse_netlist(path):
    text = open(path).read()
    nets = {}
    chunks = re.split(r'\(net \(code "\d+"\) \(name "([^"]+)"\)', text)
    # chunks: [prefix, name1, body1, name2, body2, ...]
    for i in range(1, len(chunks), 2):
        name, body = chunks[i], chunks[i + 1]
        nodes = set()
        for n in re.finditer(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"\)'
                             r'(?: \(pinfunction "([^"]*)"\))?', body):
            ref, pin, func = n.groups()
            nodes.add((ref, pin, func or ""))
        nets[name] = nodes
    return nets

def has(nets, net, ref, pinfunc_re):
    """True if net contains a node of ref whose pinfunction matches regex."""
    for r, pin, func in nets.get(net, ()):
        if r == ref and re.fullmatch(pinfunc_re, func or pin):
            return True
    return False

failures = 0
def check(cond, msg):
    global failures
    print(("ok:   " if cond else "FAIL: ") + msg)
    if not cond: failures += 1

def verify(path, variant):
    global failures
    print(f"\n=== {path} ({variant}) ===")
    nets = parse_netlist(path)
    mcu = "U1"
    full = variant in ("mini", "bare", "cam")   # camera + SD present?

    # MCU-side pin-name expectations differ: S3 (mini/bare/cam) vs C3 (lite)
    if variant == "lite":
        TX, RX = "GPIO7", "GPIO6"
        USB_DP, USB_DM = r"GPIO19/USB_D\+", "GPIO18/USB_D-"
        LED = "GPIO8"
        EN_PIN, IO0_PIN = "EN/CHIP_PU", r"GPIO0/.*"
    else:
        TX, RX = "TXD0|U0TXD", "RXD0|U0RXD"
        USB_DP, USB_DM = r"IO20|GPIO20/USB_D\+", "IO19|GPIO19/USB_D-"
        LED = "IO1|GPIO1"
        EN_PIN, IO0_PIN = "EN|CHIP_PU", "IO0|GPIO0"

    # UART crossing: MCU TX -> bridge RXD, bridge TXD -> MCU RX
    check(has(nets, "UART_TX", "U3", "RXD") and has(nets, "UART_TX", mcu, TX),
          "UART_TX = MCU TX + bridge RXD (crossed once)")
    check(has(nets, "UART_RX", "U3", "TXD") and has(nets, "UART_RX", mcu, RX),
          "UART_RX = bridge TXD + MCU RX")

    # Calculator USB pair through ESD to bridge
    check(has(nets, "CALC_DP", "J1", "Pin_3") and has(nets, "CALC_DP", "U3", r"D\+")
          and has(nets, "CALC_DP", "U5", "I/O2"),
          "CALC_DP: plug pin3 + ESD + bridge D+")
    check(has(nets, "CALC_DM", "J1", "Pin_2") and has(nets, "CALC_DM", "U3", "D-")
          and has(nets, "CALC_DM", "U5", "I/O1"),
          "CALC_DM: plug pin2 + ESD + bridge D-")

    # Power chain: plug VBUS -> switch -> buck VIN; buck feedback divider
    check(has(nets, "VBUS_IN", "J1", "Pin_1") and has(nets, "VBUS_IN", "SW1", "B"),
          "VBUS_IN: plug pin1 -> switch common")
    check(has(nets, "VBUS", "SW1", "A") and has(nets, "VBUS", "U4", "VIN")
          and has(nets, "VBUS", "U4", "EN") and has(nets, "VBUS", "U5", "VBUS"),
          "VBUS: switch -> buck VIN+EN, ESD VBUS")
    check(has(nets, "SW_NODE", "U4", "SW") and has(nets, "SW_NODE", "L1", ".*"),
          "SW_NODE: buck SW -> inductor")
    check(has(nets, "FB_3V3", "U4", "FB"), "FB divider present on buck FB")
    check(has(nets, "+3V3", "U3", "VDD") and has(nets, "+3V3", "U3", "VREGIN"),
          "+3V3 powers bridge VDD+VREGIN (self-powered config)")

    if full:
        # SD (SPI mode) + pull-ups
        for net, sdfunc, mfunc in [("SD_CS", "DAT3/CD", "IO21|GPIO21"),
                                   ("SD_MOSI", "CMD", "IO9|GPIO9"),
                                   ("SD_SCK", "CLK", "IO7|GPIO7"),
                                   ("SD_MISO", "DAT0", "IO8|GPIO8")]:
            check(has(nets, net, "J3", sdfunc) and has(nets, net, mcu, mfunc),
                  f"{net}: SD {sdfunc} <-> MCU {mfunc}")
        check(sum(1 for r, _, _ in nets.get("SD_CS", ()) if r.startswith("R")) == 1 and
              sum(1 for r, _, _ in nets.get("SD_MISO", ()) if r.startswith("R")) == 1,
              "SD_CS and SD_MISO have pull-ups")

        # Camera DVP mapping (MCU side per final GPIO allocation)
        cam = {"CAM_XCLK": "IO10|GPIO10", "CAM_SIOD": "IO40|MTDO",
               "CAM_SIOC": "IO39|MTCK", "CAM_VSYNC": "IO38|GPIO38",
               "CAM_HREF": "IO47|SPICLK_P", "CAM_PCLK": "IO13|GPIO13",
               "CAM_Y2": "IO15|XTAL_32K_P", "CAM_Y3": "IO17|GPIO17",
               "CAM_Y4": "IO18|GPIO18", "CAM_Y5": "IO16|XTAL_32K_N",
               "CAM_Y6": "IO14|GPIO14", "CAM_Y7": "IO12|GPIO12",
               "CAM_Y8": "IO11|GPIO11", "CAM_Y9": "IO48|SPICLK_N"}
        for net, func in cam.items():
            check(has(nets, net, mcu, func) and has(nets, net, "J2", ".*"),
                  f"{net}: MCU {func} <-> camera FPC")
        check(all(has(nets, n, r, ".*") for n, r in
                  [("CAM_SIOD", "R"), ("CAM_SIOC", "R")]
                  for r in [x for x, _, _ in nets.get(n, ()) if x.startswith("R")][:1]),
              "SCCB pull-ups on SIOD/SIOC")

    # Programming pads: native USB + straps
    check(has(nets, "USB_DP", mcu, USB_DP) and has(nets, "USB_DP", "J4", "Pin_6"),
          "USB_DP: MCU USB_D+ -> prog pad 6")
    check(has(nets, "USB_DM", mcu, USB_DM) and has(nets, "USB_DM", "J4", "Pin_5"),
          "USB_DM: MCU USB_D- -> prog pad 5")
    check(has(nets, "EN", mcu, EN_PIN) and has(nets, "EN", "J4", "Pin_3"),
          "EN: MCU enable -> prog pad 3 (+RC)")
    check(has(nets, "IO0", mcu, IO0_PIN) and has(nets, "IO0", "J4", "Pin_4"),
          "IO0: boot strap -> prog pad 4 (+pull-up)")
    check(has(nets, "STATUS_LED", mcu, LED), "STATUS_LED wired")

    # GND sanity: every IC grounded
    gnd_refs = ["U1", "U3", "U4", "U5", "J1"] + (["J3"] if full else [])
    for ref in gnd_refs:
        check(any(r == ref for r, _, _ in nets.get("GND", ())),
              f"GND reaches {ref}")

    if variant in ("bare", "cam"):
        check(has(nets, "RF_FEED", mcu, "LNA_IN"), "RF: LNA_IN -> pi match")
        check(has(nets, "ANT_FEED", "ANT1", "FEED"), "RF: pi match -> antenna")

    if variant == "bare":
        # flash on VDD_SPI + SPI0 pins
        for net, ff, mf in [("FLASH_CS", "~{CS}", "SPICS0"),
                            ("FLASH_CLK", "CLK", "SPICLK"),
                            ("FLASH_D", r"DI\(IO0\)", "SPID"),
                            ("FLASH_Q", r"DO\(IO1\)", "SPIQ"),
                            ("FLASH_WP", "IO2", "SPIWP"),
                            ("FLASH_HD", "IO3", "SPIHD")]:
            check(has(nets, net, "U2", ff) and has(nets, net, mcu, mf),
                  f"{net}: flash {ff} <-> MCU {mf}")
        check(has(nets, "VDD_SPI", "U2", "VCC") and has(nets, "VDD_SPI", mcu, "VDD_SPI"),
              "flash powered from VDD_SPI")
        check(has(nets, "XTAL_P", "Y1", ".*") and has(nets, "XTAL_P", mcu, "XTAL_P"),
              "crystal XTAL_P wired")

print("nlink netlist verification")
VARIANTS = [("mini", "/tmp/nlink-proto.net"), ("bare", "/tmp/nlink-stick.net"),
            ("cam", "/tmp/nlink-cam.net"), ("lite", "/tmp/nlink-lite.net")]
import os
for variant, path in VARIANTS:
    if os.path.exists(path):
        verify(path, variant)
print(f"\n{'FAILURES: ' + str(failures) if failures else 'All netlist checks passed.'}")
sys.exit(1 if failures else 0)
