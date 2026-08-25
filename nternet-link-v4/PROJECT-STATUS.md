# nternet-Link V4 — project status & folder guide

Updated 2026-08-11. This folder is the working home for the V4 overhaul of
the nternet-Link (github.com/OtterCadGH/nternet-Link).

## What's in here

| Path | What it is |
| ---- | ---------- |
| `platformio.ini`, `include/`, `src/` | V4 firmware — PlatformIO, 3 targets (xiao-s3 dev board, nlink-pcb custom board, xiao-c3-lite legacy). Framed CRC16 protocol, NVS provisioning (no secrets in source), provider-agnostic LLM client, OV5640 camera, SD storage (JPEG photos / TXT chat logs, plain FAT32). |
| `calculator/` | TI-Nspire Lua: `nlink.lua` protocol client library + `demo_app.lua`. |
| `docs/PROTOCOL.md` | Wire protocol spec (nlink v1). |
| `tools/gui_simulator.html` | Open in a browser: mini-Claude calculator UI + virtual ESP32 speaking the real protocol. Fault injection, wire log, simulated SD card. This is the reference design for the future Lua UI port. |
| `hardware/PCB-DESIGN.md` | Board engineering spec (60×12.5mm stick, part choices, power, routing rules). |
| `hardware/kicad/CAPTURE-PLAN.md` | Net tables, GPIO allocation, checklists. |
| `hardware/kicad/nlink-proto/` | **Variant A** — ESP32-S3-MINI-1-N4R2 module, ~60×16mm. Build this first. Open `nlink-proto.kicad_pro` in KiCad (7+). PDF preview included. |
| `hardware/kicad/nlink-stick/` | **Variant B** — bare ESP32-S3R8, ≤60×12.5mm. The shrink; spin after A works. |
| `hardware/kicad/generate_schematics.py` | Regenerates both schematics from the connectivity spec (needs KiCad 7+ symbol libs installed). |
| `hardware/kicad/verify_netlists.py` | Netlist verifier — 90/90 checks pass on both variants as delivered. |
| `test/` | Host-side protocol tests (C++ + Lua cross-check, 20/20 pass). |

## State of play

Done: firmware scaffold · protocol (3 implementations, cross-verified) ·
GUI simulator with mini-Claude skin · both KiCad schematics, netlist-verified ·
board outline stubs.

Next steps, in order:
1. Flash a XIAO ESP32S3 Sense with `pio run -e xiao-s3 -t upload`, smoke-test
   the protocol against `calculator/demo_app.lua`.
2. Open `nlink-proto` in KiCad: tidy symbol placement (nets live in the global
   labels — moving parts can't break connectivity), remap camera FPC J2 to the
   pinout of the actual OV5640 module you buy (current order is a placeholder,
   flagged on the schematic), pick the mini-B plug part (options in
   PCB-DESIGN.md), then layout 60×16 and order.
3. Bring up Variant A with the `nlink-pcb` firmware target.
4. Port the simulator's mini-Claude UI back to `nlink.lua`.
5. Shrink to `nlink-stick` (12.5mm, bare chip + antenna — budget one RF respin).

## Open decisions

- Exact OV5640 camera module (single-supply integrated-LDO module vs raw
  sensor flex needing 2.8V/1.2V rails) → fixes J2 pinout + camera sheet.
- Mini-B male plug mounting: board-mount part / soldered pigtail / V2-style
  edge-pad right-angle plug.
- SD socket for the stick must be ≤12.5mm wide (Hirose DM3D class);
  footprint in the files is the common DM3AT — swap before stick layout.
