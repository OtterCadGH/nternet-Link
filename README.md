# nternet-Link Project Hub

### Open Hardware Platform for TI-Nspire CX & CX II Connectivity

This repository documents a series of projects that enable the TI-Nspire calculator to communicate with external hardware and the internet.

Across three generations the project evolved from a physical calculator modification into a fully external plug-in communication device and now into a modular wireless embedded platform.

The goal is to turn the TI-Nspire into a programmable handheld computer capable of networking, messaging, and interacting with modern APIs.

---

## Which Guide Should I Follow?

This repository contains **three separate builds**.
Each represents a different stage of the project and a different level of difficulty.

| Version | What It Is                                           | Skill Level          | Recommended?        |
| ------- | ---------------------------------------------------- | -------------------- | ------------------- |
| V1      | Internal hardware modification (Ti-GPT)              | Advanced soldering   | No, legacy          |
| V2      | External USB wireless adapter (nternet-Link ESP32C3) | Moderate             | Yes, starting point |
| V3      | Modular expansion platform (ESP32S3 + Camera + LoRa) | Moderate to Advanced | Current development |

Open the guide that matches the device you want to build.

---

## V1 — Ti-GPT (Internal Modification)

**Read here → `docs/README.V1.md`**

The original proof of concept.

This version installs an ESP32 inside the calculator and wires directly into the motherboard USB lines.
It enabled the first ChatGPT interface running on a TI-Nspire calculator.

Important:
This version requires opening the calculator and permanently modifying it.
It is preserved as a historical reference and learning resource.

---

## V2 — nternet-Link (ESP32C3 Adapter)

**Read here → `docs/README.V2.md`**

The first practical and recommended version.

This design moves all electronics outside the calculator and connects through the USB mini port.
No calculator modification is required.

Features:
• USB serial communication
• wireless networking
• Lua applications
• ChatGPT interface
• file and string transfer

This is the best place to start.

---

## V3 — nternet-Link Modular Platform (ESP32S3)

**Read here → `docs/README.V3.md`**

Current active development.

This version upgrades to the XIAO ESP32S3 and introduces expansion hardware.

Planned and working capabilities:
• camera capture
• photo to LLM API interaction
• LoRa communication
• Meshtastic messaging
• calculator to calculator wireless communication

The device effectively becomes a networked handheld terminal for the calculator.

---

## What This Project Is

This project explores extending legacy educational hardware using modern embedded systems.

The TI-Nspire provides:
• keyboard
• display
• scripting environment (Lua)

The ESP32 provides:
• networking
• processing
• sensors
• wireless communication

Together they form a small programmable handheld computer platform.

---

## Project Philosophy

The nternet-Link is designed to be:

• non destructive to the calculator
• reproducible
• inexpensive
• hackable
• educational

All hardware and software are open source.

---

## Not Affiliated

This project is not affiliated with or endorsed by Texas Instruments. Definetly not.

---
## Academic Integrity Notice

This project is an embedded systems and communication interface experiment.

It is not designed, intended, or marketed as a tool for use during examinations.

Many schools and testing environments prohibit electronic communication devices, programmable computers, or modified calculators. You are responsible for following the rules of your institution.

The author does not encourage, support, or condone using this project to gain unfair academic advantage or to bypass testing policies.

This repository exists for learning about:
• USB communication
• serial protocols
• embedded networking
• hardware interfacing
• software integration

If you bring this device into an exam, that is your decision and your responsibility. Dont be that guy.

---
YouTube demonstrations and development logs will accompany future releases.
