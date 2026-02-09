# nternet-Link

### Open Source Wireless Link Adapter for TI-Nspire CX & CX II Calculators

The **nternet-Link** is an open source hardware and software alternative to the TI-Navigator wireless adapter.

It allows a TI-Nspire CX or CX II calculator to communicate with an external microcontroller over the calculator USB mini port.
This implementation uses a Seeed Studio XIAO ESP32C3 to act as a serial bridge and WiFi client, enabling data transfer, network communication, and internet connectivity for the calculator.

The project began as a proof of concept serial link and evolved into a system capable of making network requests, including a demonstration application that connects the calculator to ChatGPT through a Lua interface.

Demo: https://youtube.com/shorts/zKWZ0URra5Q?si=NUPr6w3lMf3OUgO9
---

## What It Does

The device plugs into the calculator USB mini port and creates a USB serial connection.
The ESP32C3 interprets data coming from the calculator and can:

• exchange strings and files

• act as a wireless communication bridge

• connect the calculator to the internet

• send and receive API requests

• run a ChatGPT style messaging interface on the calculator

• Run any App w/ and w/o internet capabilities

• Store Data

No modification to the calculator hardware is required.

---

## Bill of Materials

Gather the following components before beginning construction:

* Seeed Studio XIAO ESP32C3
* CP2102 USB to UART bridge module
* 90° right angle slim USB Mini male connector
* 5.6 mm toggle switch (optional)
* hookup wire (28 to 32 AWG recommended)
* soldering iron and solder
* hot glue
* 3D printed enclosure (provided in /hardware)

![IMG_0172](https://github.com/user-attachments/assets/b5b608ab-d715-4918-aa3a-acfc84911b07)


---

## Step 1 — Prepare the CP2102

![IMG_0171](https://github.com/user-attachments/assets/e28f3843-c6d0-42ba-92a9-76df890ad08f)


The CP2102 board must be stripped down.

Remove:
• the USB connector
• the dupont header pins

After removal, solder wires directly to the pads:

### USB Side

| Signal | Wire Color |
| ------ | ---------- |
| VBUS   | Red        |
| GND    | Black      |
| D+     | Green      |
| D−     | White      |

### UART Side

| Signal | Wire Color |
| ------ | ---------- |
| 5V     | Red        |
| GND    | Black      |
| TXD    | Blue       |
| RXD    | Yellow     |

---

## Step 2 — Attach the USB Mini Connector

Solder the USB Mini connector to the USB pads of the CP2102:

Match the signals exactly:

D+ → D+
D− → D−
VBUS → VBUS
GND → GND

This connector plugs directly into the calculator.

---

## Step 3 — Connect to the ESP32C3

Wire the CP2102 UART pins to the XIAO ESP32C3:

| CP2102 | ESP32C3 |
| ------ | ------- |
| TXD    | RX      |
| RXD    | TX      |
| 5V     | VIN     |
| GND    | GND     |

Important:

* TX and RX are crossed (TX → RX and RX → TX)
* Grounds must be common across all devices

Optional:
You may install the toggle switch inline with the 5V line coming from the USB Mini connector to act as a power switch.

![IMG_0167](https://github.com/user-attachments/assets/2fd89cca-2656-4422-b1d0-5f484fb627b8)

---

## Step 4 — Install Into the Case

![IMG_0168](https://github.com/user-attachments/assets/79d9b5f7-eb15-4aac-a6d7-50341b254977)


Place the full assembly into the provided 3D printed enclosure.

Ensure:
• the USB Mini connector aligns with the opening
• the ESP32C3 USB-C port remains accessible

---

## Step 5 — Final Assembly

![IMG_0170](https://github.com/user-attachments/assets/8dced8b9-0d18-4a25-be3e-4d9d154370bd)

Insert the toggle switch into the rear sleeve.

Then secure the electronics using hot glue:

Important:
Do NOT cover the ESP32C3.
The board must be able to pivot upward so code can be uploaded over USB-C.

The enclosure is designed so the ESP32C3 can hinge outward for programming.

![0](https://github.com/user-attachments/assets/cd4e8b00-0bc1-408f-be8c-0242ab5a403d)


---
## Step 5 — Final Assembly
Insert Nternet-Link Into calculator!

![435543](https://github.com/user-attachments/assets/15619c37-6487-4e40-8e00-2dd8315ed055)


Watch the Demo Here:

https://youtube.com/shorts/zKWZ0URra5Q?si=NUPr6w3lMf3OUgO9

---

## Demo Applications

### Serial Echo Demo

A simple Lua program running on the calculator sends a string to the ESP32C3.

The ESP32C3 immediately returns the same string.

This verifies:
• USB communication
• UART communication
• calculator software communication

---

### ChatGPT Demo

A second demonstration expands the concept.

The calculator Lua application:
• accepts user text input
• sends the string to the ESP32C3

The ESP32C3:
• connects to WiFi
• performs a ChatGPT API request
• returns the response

The calculator then renders a chat style interface directly on the screen.

The result is a functional conversational interface entirely running from a graphing calculator.

---

## Software

Calculator software is written in Lua using the TI-Nspire Lua API.

ESP32 firmware is written in Arduino framework for ESP32C3.

Both are provided in the `/software` directory.

---

## Open Source

All hardware, firmware, and calculator software are released open source.

You are encouraged to modify, improve, and redistribute this project.

---

## Disclaimer

This project is not affiliated with or endorsed by Texas Instruments.

Use at your own risk. Improper wiring may damage your calculator.

---
## Next Version (In Development)

A second generation of the nternet Link is already functional and currently being documented.

The new revision replaces the XIAO ESP32C3 with the **Seeed Studio XIAO ESP32S3**.
This upgrade was chosen because the ESP32S3 supports native USB and expansion boards, which significantly increases the capabilities of the device.

The ESP32S3 version can host Seeed Studio expansion modules including:

• Camera module (live image capture experiments)
• LoRa radio module
• Meshtastic compatible mesh networking communication

This opens the possibility of calculator to calculator wireless messaging over long distances without WiFi infrastructure.

The hardware is complete and operational.
Documentation is being prepared in video format showing assembly and operation.

I am currently collaborating with another developer who is leading major improvements to the software architecture while I focus on hardware design, electrical interfacing, and integration with the TI Nspire Lua environment.

The next revision will include:
• improved communication protocol
• cleaner serial handling
• easier firmware installation
• expanded Lua user interface
• support for additional peripherals

Source code and instructions for the ESP32S3 version will be released in this repository once the software layer is finalized.
Designed and developed by William Otterson
Mechanical Engineering, The University of Texas at Austin
