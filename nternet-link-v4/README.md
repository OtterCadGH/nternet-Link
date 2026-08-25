# nternet-Link V4

Ground-up rewrite of the nternet-Link firmware and protocol, targeting the
custom V4 PCB (ESP32-S3 + camera + microSD) and the existing XIAO ESP32S3
dev hardware.

```
nternet-link-v4/
├── platformio.ini          build targets: xiao-s3, nlink-pcb, xiao-c3-lite
├── include/nlink_config.h  pins + feature flags per board
├── src/
│   ├── main.cpp            command dispatch, WiFi, watchdog
│   ├── nlink_proto.*       framed CRC16 wire protocol (codec + link)
│   ├── provisioning.*      NVS config — no secrets in source, ever
│   ├── llm_client.*        provider-agnostic LLM client (OpenAI-compatible)
│   ├── camera_module.*     OV5640 capture + autofocus
│   └── storage.*           microSD: JPEG photos, TXT chat logs, files
├── calculator/
│   ├── nlink.lua           reference client library (framing, CRC, retries)
│   └── demo_app.lua        minimal app proving the protocol end-to-end
├── docs/PROTOCOL.md        wire protocol spec
└── hardware/PCB-DESIGN.md  KiCad board design: BOM, pin map, layout rules
```

## What's different from V3

| | V3 | V4 |
| - | -- | -- |
| Protocol | magic strings, `delay()` pacing, no checksums | framed, CRC16 per frame + per body, ack/retry, resyncs through noise |
| Secrets | API key + WiFi hardcoded in the .ino | NVS-stored, set from the calculator (`CFG SET llm.key ...`), masked on read |
| LLM | Groq hardcoded | any OpenAI-compatible endpoint: Groq, OpenAI, OpenRouter, local ollama |
| JSON | string concatenation | ArduinoJson build + filtered parse |
| Storage | none | microSD — photos as JPEG, chat as TXT, readable in any computer |
| Structure | one 711-line .ino | PlatformIO modules, three board targets |
| Calc side | one 1,157-line file | `nlink.lua` library + thin apps |

## Quick start (XIAO ESP32S3 Sense)

```bash
pio run -e xiao-s3 -t upload
```

Then from the calculator demo app (or the USB-C serial console):

```
CFG SET llm.key gsk_yourkey
CFG SET llm.base https://api.groq.com/openai/v1
WIFI YourNetwork<TAB>yourpassword     # or use the app's WiFi picker
ASK hello
SNAP
```

Settings persist across reboots. Photos land in `/PHOTOS`, transcripts in
`/CHAT` on the SD card.

## Status

- [x] Protocol codec (C++ + Lua, cross-verified)
- [x] Provisioning, LLM client, camera, SD storage
- [ ] Compile + hardware test on XIAO S3 (needs the physical board)
- [ ] Full calculator app UI (port of the V3 interface onto nlink.lua)
- [ ] KiCad schematic capture from hardware/PCB-DESIGN.md
- [ ] LoRa/Meshtastic module support

## Academic integrity

Same stance as always: this is an embedded systems project. It is not
designed or intended for use during examinations. Follow your institution's
rules — don't be that guy.
