# nternet-Link

**An open-hardware platform that turns a TI-Nspire graphing calculator into a
networked handheld terminal** — Wi-Fi, an AI chat/tutor, a camera that reads
and solves problems, and onboard storage, through a small plug-in device.

Over four generations the project grew from a soldered-in modification into a
clean, reproducible, plug-in platform with a proper communication protocol and
custom PCBs.

💬 [Discord](https://discord.gg/6HgRHHB2q)

> **Not affiliated with or endorsed by Texas Instruments.** This is an
> embedded-systems and networking experiment. It is **not** designed or
> intended for use during exams — follow your institution's rules.

---

## ▶ Try the calculator interface in your browser

The V4 calculator UI runs as a live simulator — the on-screen calculator and a
virtual ESP32 talk over the *real* V4 wire protocol, so you can experiment with
the whole experience before building anything.

[![nternet-Link V4 GUI simulator](docs/img/simulator.png)](v4/tools/gui_simulator.html)

**[🖥 Open the live simulator →](https://ottercadgh.github.io/nternet-Link/v4/tools/gui_simulator.html)**
· or download [`v4/tools/gui_simulator.html`](v4/tools/gui_simulator.html) and
open it in any browser (runs fully offline).

---

## Which version should I look at?

**→ Build [V4](v4/). It's the current, recommended generation.** The others are
here as history and reference.

| | Version | What it is | Build it? |
| --- | --- | --- | --- |
| 🟢 | **[V4](v4/)** | Rewritten firmware + protocol + UI. Two custom PCBs: a full **camera** stick and a tiny **chat-only** board. Browser simulator, automated tests. | **Yes — start here** |
| ⚪ | [V3](v3/) | First ESP32-S3 + camera platform, with a host proxy server. | Superseded |
| ⚪ | [V2](v2/) | First external USB plug-in adapter (ESP32-C3). No calculator mod. | Superseded |
| ⚪ | [V1](v1/) | The original — an ESP32 soldered *inside* the calculator. | Legacy / reference |

---

## How it works

```
 TI-Nspire  ──USB──►  nternet-Link device  ──Wi-Fi──►  AI provider
 (keyboard,           (ESP32 + USB bridge                (Groq / OpenAI /
  screen, Lua)         + camera + SD)                     OpenRouter / local)
```

The calculator supplies the keyboard and screen and runs a Lua app. The device
is an ESP32 that bridges USB-serial to Wi-Fi, calls an AI API, drives a camera,
and stores photos and chat logs on a microSD card. In V4 the two sides speak
**nlink v1**, a framed protocol with CRC checks and automatic retries.

---

## Repository layout

```
├── README.md          you are here — project hub
├── docs/              shared assets (hub images)
├── v1/                Ti-GPT — internal mod (legacy)
│   ├── firmware/      ESP32 .ino
│   └── calculator/    Lua app + .tns
├── v2/                external adapter (docs)
├── v3/                ESP32-S3 + camera platform
│   ├── firmware/      ESP32 .ino
│   ├── calculator/    Lua app + .tns
│   └── server/        host proxy server
└── v4/                ← CURRENT: full rewrite
    ├── README.md      tutorial + build guide (start here)
    ├── src/ include/  ESP32 firmware (C++)
    ├── calculator/    TI-Nspire Lua client + demo
    ├── tools/         browser GUI simulator
    ├── docs/          protocol spec
    ├── test/          host-side tests
    └── hardware/      PCB design + 4 KiCad board variants
```

Each version folder has its own README. **New here? Open [`v4/`](v4/).**

---

## The story

**V1 (2025)** proved the concept by soldering an ESP32 onto the calculator's
USB lines. **V2** moved all the electronics *outside* into a plug-in adapter —
no calculator modification. **V3** jumped to the ESP32-S3 with a camera and a
host proxy. **V4** is the ground-up rewrite: a reliable checksummed protocol,
no API keys in the source (they live in the device's flash), any
OpenAI-compatible AI provider, a browser simulator, automated tests, and two
custom circuit boards.

## License / spirit

Open hardware and software — modify, improve, and share. Built for learning
about USB, serial protocols, embedded networking, and hardware interfacing.
