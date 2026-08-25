# nlink wire protocol v1

Framed, checksummed, ASCII-safe protocol between the calculator (TI-Nspire Lua
via the ASI serial API) and the nternet-Link device. Replaces the V3 ad-hoc
text protocol (`LEN:` / `RESULT:` / `>>>END<<<`).

## Design constraints

- The Nspire ASI API delivers data as strings with no guaranteed chunk
  boundaries, so frames are **newline-delimited printable ASCII** (payloads are
  base64) rather than raw binary.
- UART at 115200 with small calculator-side buffers → frames are kept under
  512 bytes on the wire.
- Corruption must be detectable → every frame carries a CRC16, and full
  responses carry an end-of-body CRC.

## Frame format

```
~1 <type> <seq> | <payload-b64> | <crc> \n
```

Written without spaces, e.g. `~1C01|UElORw==|3AF2\n`

| Field       | Size    | Meaning                                            |
| ----------- | ------- | -------------------------------------------------- |
| `~1`        | 2       | Start marker + protocol version                    |
| type        | 1       | Frame type (letter, below)                         |
| seq         | 2 (hex) | Sequence number 00–FF, wraps                       |
| payload-b64 | 0–484   | Base64 of the payload (may be empty)               |
| crc         | 4 (hex) | CRC16-CCITT (poly 0x1021, init 0xFFFF) over `type + seq + "|" + payload-b64` |

Anything on the wire that is not part of a valid frame is ignored (the parser
resyncs on `~1`), so debug prints and boot noise can never corrupt state.

## Frame types

| Type | Direction     | Meaning                                                    |
| ---- | ------------- | ---------------------------------------------------------- |
| `H`  | calc → device | Hello / handshake. Payload: `NLINK,<client-version>`       |
| `h`  | device → calc | Hello reply. Payload: `NLINK,<fw-version>,<caps>` (caps: `cam,wifi,lora`) |
| `C`  | calc → device | Command (payload = command text, see below)                |
| `A`  | device → calc | Ack: command with that seq accepted and started            |
| `N`  | either        | Nak: frame with that seq rejected/corrupt — resend         |
| `S`  | device → calc | Status/event text (`PROCESSING`, `WIFI OK <ip>`, `NETWORKS <list>`) |
| `D`  | device → calc | Response body chunk (in-order)                             |
| `E`  | device → calc | End of body. Payload: `<total-len>,<crc16-of-body-hex>`    |
| `X`  | device → calc | Error text (terminates the operation)                      |

## Commands (payload of `C` frames)

```
PING                      → S:PONG
INFO                      → D/E body: JSON device info
SNAP                      → A, S:PROCESSING, D…D, E   (capture + vision model)
ASK <text>                → A, S:PROCESSING, D…D, E   (text model, with history)
CLEAR                     → S:CLEARED                  (reset chat history)
SCAN                      → S:NETWORKS a(-52dB)|b(-70dB)|…
WIFI <ssid>\t<password>   → S:WIFI OK <ip> | S:WIFI FAIL
CFG SET <key> <value>     → S:OK        (keys: wifi.ssid wifi.pass llm.key
                                          llm.base llm.model llm.vmodel llm.sys)
CFG GET <key>             → S:CFG <key>=<value>  (secrets masked)
LS [dir]                  → A, D…D, E   body: "name<TAB>size" per line
GET <name>                → A, D…D, E   body: file contents (from /FILES)
PUT <name>\t<contents>    → S:OK        (writes to /FILES)
NEWCHAT                   → S:CLEARED   (new transcript file + clear history)
RESET                     → S:OK        (clear busy state)
REBOOT                    → S:REBOOTING (full restart)
```

## SD card layout (user-legible)

Everything on the card is plain FAT32 with ordinary formats — pop it into any
computer and read it directly:

```
/PHOTOS/IMG_0042.JPG           every capture, saved before the API call
/CHAT/2026-08-11_CHAT_003.TXT  plain-text transcripts, one file per session
/FILES/...                     files pushed from the calculator (PUT/GET)
```

During SNAP the device emits `S:SAVED /PHOTOS/IMG_0042.JPG` as soon as the
photo is on the card, before the model reply arrives.

## Reliability rules

- Device acks (`A`) every accepted command; calculator retries a command up to
  2× if no `A`/`S` arrives within 2 s.
- A frame with a bad CRC gets `N` with the same seq; sender resends once.
- Body chunks (`D`) are sent in seq order; the `E` frame's length + CRC lets
  the calculator verify the whole body and request a full retry (`N`) if bad.
- Device paces chunks (~5 ms gap) — no flow-control needed at 115200.
- One operation at a time: a `C` while busy gets `X:BUSY`.
