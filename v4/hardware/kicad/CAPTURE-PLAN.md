# KiCad capture plan — nternet-Link V4 (dual variant)

Decision on record: **both stacks in one project family.**

- **Variant A `nlink-proto`** — ESP32-S3-MINI-1-N4R2 module, board ~60×16 mm.
  Pre-certified RF, no antenna design. This is the board you build first and
  debug everything on. (Note the exact part: **-N4R2** — the plain -N8 has NO
  PSRAM and the camera framebuffer needs PSRAM.)
- **Variant B `nlink-stick`** — bare ESP32-S3R8 + W25Q64 flash + chip antenna,
  board ≤60×12.5 mm. The shrink. Only spin this after Variant A works, so RF
  matching is the only new risk on the board.

## How to structure this in KiCad (no native variant support)

Two projects, **sharing sheet files**. Hierarchical sheets are plain files, so
both projects reference the same shared sheets and diverge only on the MCU/RF
sheet:

```
hardware/kicad/
├── shared/
│   ├── power.kicad_sch         VBUS → switch → buck → 3V3
│   ├── usb_bridge.kicad_sch    mini-B plug, ESD, CP2102N
│   ├── camera.kicad_sch        24-pin FPC, DVP bus
│   ├── sd.kicad_sch            microSD, SPI
│   └── program.kicad_sch       TC2030/pogo pads, straps, LED
├── nlink-proto/                Variant A project
│   ├── nlink-proto.kicad_pro
│   ├── nlink-proto.kicad_sch   root: instantiates shared + mcu_mini
│   └── mcu_mini.kicad_sch      ESP32-S3-MINI-1-N4R2
└── nlink-stick/                Variant B project
    ├── nlink-stick.kicad_pro
    ├── nlink-stick.kicad_sch   root: instantiates shared + mcu_bare
    └── mcu_bare.kicad_sch      S3R8 + flash + crystal + RF/antenna
```

Same net names on both MCU sheets → shared sheets don't care which variant
they're in. Layout is per-project (two .kicad_pcb), which is unavoidable —
they're different board outlines anyway.

Stock symbols: `RF_Module:ESP32-S3-MINI-1`, `Interface_USB:CP2102N-A02-GQFN24`,
`MCU_Espressif:ESP32-S3` (bare). Pin numbers come from these library symbols —
the tables below specify connectivity by signal name; trust the symbol, not
memory, for pad numbers.

## Final GPIO allocation (both variants — identical firmware)

Verified against constraints: flash pins 26–32 untouched; octal-PSRAM pins
35/36/37 untouched (matters on S3R8); strapping pins 0/3/45/46 used only for
their strap roles or left alone.

| Net | GPIO | | Net | GPIO |
| --- | ---- |-| --- | ---- |
| UART_TX (→ bridge RXD) | 43 | | CAM_Y4 | 18 |
| UART_RX (← bridge TXD) | 44 | | CAM_Y5 | 16 |
| SD_SCK | 7 | | CAM_Y6 | 14 |
| SD_MISO | 8 | | CAM_Y7 | 12 |
| SD_MOSI | 9 | | CAM_Y8 | 11 |
| SD_CS | 21 | | CAM_Y9 | 48 |
| USB_D− (program pad) | 19 | | CAM_VSYNC | 38 |
| USB_D+ (program pad) | 20 | | CAM_HREF | 47 |
| CAM_XCLK | 10 | | CAM_PCLK | 13 |
| CAM_SIOD (SCCB SDA) | 40 | | BOOT strap (pad) | 0 |
| CAM_SIOC (SCCB SCL) | 39 | | STATUS_LED | 1 |
| CAM_Y2 | 15 | | CAM_Y3 | 17 |

This is exactly the `NLINK_BOARD_CUSTOM_PCB` map already in
`include/nlink_config.h` — firmware needs zero changes for either variant.

## Net tables per sheet

### power.kicad_sch
| Net | Connections | Notes |
| --- | ----------- | ----- |
| VBUS | J1.VBUS → SW1 → U_BUCK.VIN, ESD.VBUS | 22 µF X5R at buck input |
| +3V3 | U_BUCK out → everything | 2×100 µF X5R bulk + 10 µF near MCU, camera, SD |
| GND | common | stitch generously on L2 |

Buck per datasheet application circuit (TPS62A02/TLV62569 class: 2.2 µH,
FB divider for 3.3 V if adjustable part). Keep the switch node tiny and far
from CAM_SIOD/SIOC and the RF end.

### usb_bridge.kicad_sch
| Net | Connections |
| --- | ----------- |
| VBUS, GND | J1 (mini-B plug) pins 1/5; J1.ID leave NC |
| CALC_D− / CALC_D+ | J1 → USBLC6 → CP2102N D−/D+ (90 Ω pair) |
| UART_TX | CP2102N RXD ← MCU GPIO43 (names cross: MCU TX → bridge RXD) |
| UART_RX | CP2102N TXD → MCU GPIO44 |
| CP2102N support | VDD+VREGIN to +3V3 (self-powered config), 100 nF + 4.7 µF decoupling, RSTb 1 k pull-up to +3V3 |

CP2102N runs from the buck's 3V3 (self-powered), not from its internal
regulator — one less heat source, and it stays alive if VBUS sags.

### camera.kicad_sch
| Net | Connections |
| --- | ----------- |
| CAM_* (14 signals) | FPC J2 ↔ MCU per GPIO table |
| +3V3 / +2V8 / +1V2 | check the exact OV5640 module: XIAO-Sense-style modules integrate the LDOs and take a single supply; a raw OV5640 flex needs 2.8 V + 1.2 V LDOs. Spec the module you'll actually buy before capture. |
| SCCB | 4.7 k pull-ups on SIOD/SIOC to the sensor I/O rail |

### sd.kicad_sch
| Net | Connections |
| --- | ----------- |
| SD_SCK/MISO/MOSI/CS | socket ↔ MCU per GPIO table; 10 k pull-ups on CS and MISO (DAT0) to +3V3 |
| CD (card detect) | optional → GND-switching pin; firmware currently polls `SD.begin`, so NC is fine |
| +3V3 | 10 µF at the socket |

### program.kicad_sch
| Net | Connections |
| --- | ----------- |
| USB_D+/D− | GPIO19/20 → TC2030 / pogo pads (this is native USB — flashing and serial debug, no bridge chip needed) |
| EN | 10 k to +3V3 + 100 nF to GND (power-on reset RC); to pad |
| IO0 | 10 k pull-up; to pad (short to GND while plugging in = bootloader) |
| +3V3, GND | pads |
| STATUS_LED | GPIO1 → R 470 Ω → LED → GND |

### mcu_mini.kicad_sch (Variant A only)
ESP32-S3-MINI-1-N4R2: 3V3 + GND (all thermal pads), 100 nF + 10 µF decoupling,
nets per GPIO table. That's the whole sheet — the module absorbs flash,
crystal, and RF.

### mcu_bare.kicad_sch (Variant B only)
Everything the module was hiding, per Espressif's ESP32-S3 hardware design
guidelines:
- S3R8 QFN56, exposed pad to GND with via farm
- W25Q64JV on the SPI0 flash pins, short matched fanout
- 40 MHz crystal + load caps (value from crystal CL and layout parasitics)
- VDD decoupling network per guidelines (bulk + 100 nF per VDD group)
- LNA pin → π-match (C-L-C, placeholder 0402s) → 2450AT18B100 antenna,
  50 Ω trace, ground keepout
- VDD_SPI strap: GPIO45 low (3.3 V flash) — check strap table during capture

## Capture order (recommended)

1. Draw the five shared sheets first; ERC with a dummy MCU sheet.
2. `nlink-proto` root + mcu_mini → full ERC clean → layout 60×16 → order.
3. Bring up Variant A end-to-end with the V4 firmware (`nlink-pcb` target).
4. Only then draw mcu_bare, clone layout intent into `nlink-stick` at 12.5 mm.

## Checklists

ERC: no unconnected CAM_* (14 nets is easy to miscount), UART TX/RX crossed
exactly once, one GND symbol per sheet, power flags on VBUS/+3V3.

DRC/layout: 90 Ω on CALC_D± and USB_D± · DVP bus < 25 mm, no vias under the
FPC · antenna keepout all layers (B only) · switch-node clearance ·
mini-B plug mechanical strain relief (through-hole tabs or edge-castellation) ·
print 1:1 and physically test-fit plug + SD card + camera flex before ordering.
