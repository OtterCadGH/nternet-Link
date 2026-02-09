# nternet-Link V3

### Development Preview

nternet-Link V3 is the current generation of the project and is still under active development.

This version moves beyond a simple wireless adapter and turns the TI-Nspire calculator into a modular embedded terminal capable of interacting with external hardware and modern network services.

The system now uses the **Seeed Studio XIAO ESP32S3** platform and supports expansion peripherals rather than a fixed configuration.

---

## What It Enables

Working demonstrators currently include:

• calculator text interface to network services
• API communication through the ESP32S3
• image capture experiments
• long range wireless messaging experiments

The calculator provides the display and input, while the ESP32S3 handles communication, processing, and peripherals.

---

## Expansion Direction

The platform is being designed to support attachable modules such as:

• camera input hardware
• LoRa radio communication
• Meshtastic style messaging networks

This allows calculator to calculator communication and off grid messaging without WiFi infrastructure, as well as interaction with remote services.

---

## Project Status

The hardware platform is operational and multiple prototypes are working.

I am currently collaborating with another developer who is focusing on the software architecture and communication protocol while I continue hardware integration and Lua interface development.

Before release, the goal is to:
• stabilize the firmware
• simplify installation
• improve reliability
• document operation clearly

Once the system is polished and reproducible, full documentation and source release will be published in this repository along with a video build and demonstration.

---

## Purpose

This project explores extending legacy educational hardware using modern embedded systems and networking.

The calculator acts as a portable human interface while the external device provides connectivity and processing.

---

## Academic Use

This project is provided for learning and experimentation only and is not intended for use in examinations or to bypass institutional policies. Users are responsible for following the rules of their school or testing environment.

---

## Disclaimer

This project is not affiliated with or endorsed by Texas Instruments.
