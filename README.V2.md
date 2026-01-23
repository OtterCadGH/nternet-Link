# Ti-GPT (V1) by FusionTechWorks <img width="42" alt="Screenshot 2025-03-27 at 5 01 29 PM" src="https://github.com/user-attachments/assets/e601bfaa-11de-4ee2-ac2a-95db41efcc50" />

## Project Status Update

This repository documents the original Ti-GPT V1 implementation. While this project originally started as a YouTube video walkthrough, development has since taken a different direction and expanded beyond the scope of that initial video.

I am currently working on a clean V2 redesign and will be publishing it in a **new dedicated repository** once it is ready. V2 focuses on improved hardware integration, cleaner power and signal routing, and a more refined software experience.

This repository remains available as a reference for the original concept, hardware exploration, and early implementation details.

## About This Repository

**This Repository is a how-to guide associated with a YouTube video project to enable a Ti-Nspire CX (and others) with Chat-GPT utilizing an ESP32C3 and native .LUA app.**

- Link to Video: LINK  
- Link for 3D printable Replacement Ti-nspire cx series slide cover: [LINK](https://www.thingiverse.com/thing:7279226)

## TI-Nspire CX Modification Guide

### Preparation and Disassembly

#### Determine Calculator Model

- There is some room for confusion here; I refer to two generations of the CX: the CX Gen 1 and CX Gen 2. Note that the CX Gen 2 is not the CX II. For more clarification, see images below.
- The first generation of the CX, including the CX and CX CAS, had issues with driver compatibility and featured a larger TiHub chip and larger battery area took up significant internal space.
- The CX CAS Gen 2, CX II, CX II CAS, CX II-T, and CX II-T CAS, is based on the newest TI chipset with a large motherboard and an integrated TiHub chip, offering minimal internal space.
- The CX Gen 2 is the best model for this project because it is based on the early chipset with the updated smaller battery and smaller TiHub chip.
- Note: The CX CAS Gen 2, CX II, CX II CAS, CX II-T, and CX II-T CAS are capable of undergoing this modification, but the extra 1.2mm of space in the CX Gen 1 is crucial for my needs.
- The CX Gen 2 can be distinguished from other variants by its white sides, full white back, smaller battery hatch, and navy blue front. The CX Gen 2 has white sides but a navy back and a larger square battery cover.
- More details on the internal discrepancies and visuals can be found in the video and photos below.

<img width="625" alt="Screenshot 2025-03-31 at 9 25 25 PM" src="https://github.com/user-attachments/assets/e0e21631-d475-4de2-b84d-d5e3d1b5726c" />
<img width="269" alt="Screenshot 2025-03-28 at 9 30 49 AM" src="https://github.com/user-attachments/assets/2c23bc80-d546-41c3-9b8f-1d1c22197ea7" />

#### Open the Battery Housing

- Use a small Phillips screwdriver to remove the battery housing cover.
- Take out the panel and the battery to expose hidden safety screws.

<img width="538" alt="Screenshot 2025-03-27 at 4 37 32 PM" src="https://github.com/user-attachments/assets/d7f32721-48a1-4765-b94e-82c22668a43f" />

#### Remove Hidden Screws

- With a one-millimeter flathead screwdriver, remove the safety screws hidden under the battery cover.
- Check under the top rubber feet for additional hidden screws. Ignore the lower feet, as there are no screws there.

<img width="289" alt="Screenshot 2025-03-27 at 4 43 18 PM" src="https://github.com/user-attachments/assets/e1fcf943-82b6-475a-b17e-463cdc8429da" />
<img width="335" alt="Screenshot 2025-03-27 at 4 38 57 PM" src="https://github.com/user-attachments/assets/722ee76c-1327-44f4-a63b-e05dea1c0b29" />

#### Remove Torx Screws

- At the bottom of the calculator, remove the Torx T-6 screws.
- Keep all small parts in a safe place. Note that the CAS, CX II, and CX II CAS models have extra screws under the front fascia.

<img width="243" alt="Screenshot 2025-03-27 at 4 39 34 PM" src="https://github.com/user-attachments/assets/e481bb73-95d8-4546-8a15-f7afb344643f" />

#### Wedge Off the Rear Housing

- Use guitar picks or similar pry tools to gently separate the rear housing from the body, working your way around the sides until the back pops off.

<img width="423" alt="Screenshot 2025-03-27 at 4 40 15 PM" src="https://github.com/user-attachments/assets/8f25f642-39d9-4aa7-8a43-59c65f6647bb" />

#### Prepare the Motherboard

- Cover the lower motherboard face with vinyl or electrical tape to prevent any interference with the piggyback.

<img width="522" alt="Screenshot 2025-03-27 at 4 40 53 PM" src="https://github.com/user-attachments/assets/a0dd5692-d11a-464b-9b5f-627da6b24cdd" />

### Micro USB Port and Wiring

#### Address Micro USB Port

- Note that Texas Instruments reversed the pinout on the CX II; the labels are upside down. Be very careful when soldering to these pins.

<img width="434" alt="Screenshot 2025-03-27 at 4 44 14 PM" src="https://github.com/user-attachments/assets/aa482438-99f0-4fe7-90e1-2dcdc5a427e5" />
<img width="214" alt="Screenshot 2025-03-27 at 4 44 27 PM" src="https://github.com/user-attachments/assets/ba037720-3170-453b-94d1-d6da575a069f" />

#### Solder and Install Piggyback, Switches, and Connector

- Refer to the provided wiring diagram to install two switches, one for grounding the ID pin to enable host mode and the other as the main power switch for the piggyback.
- Add optional a magnetic connector to facilitate easy assembly and disassembly.
- Note pinout lables are reversed for the CX II
- Note between ESP32 and CP2102 RX -> TXD, TX -> RXD in UART communication protocol but between Ti-nspire motherboard and CP2102 D+ -> D+, and D- -> D- in USB communication protocol.

<img width="1427" alt="Screenshot 2025-03-27 at 11 05 36 PM" src="https://github.com/user-attachments/assets/a837bfc3-31a8-47c1-bb90-9fe1b2f05daa" />

#### Adjust Internal Space

- Use necessary tools to free up internal space as needed of the calculator to accommodate the piggyback and switches.
- Optionally add USB access to the ESP for debugging purposes while it's still in the case. Heres an example of mine.

### Software Installation and Configuration

#### Download and Install Software

- Download the TI-nspire CAS student software free trial and install it.
- Use this software to upload the .LUA file from the provided GitHub link to your calculator.

https://education.ti.com/fr/software/details/en/B4F6E4EE05B94D75AAB4DFE24B2720AE/ti-nspirecxcas_pc_trial

#### Setup API and Arduino

- Follow the guide by Anders Jensen to create your ChatGPT API secret key. (GUIDE LINK)
- Download and install the Arduino IDE and the necessary drivers for your ESP model.
- Edit the .INO file from this repository to include your API secret key and Hotspot or Wi-Fi details.
- Note for iphones enable Maximise Compatibility to allow your esp to connect in hotspot settings.

<img width="381" alt="Screenshot 2025-03-27 at 4 56 32 PM" src="https://github.com/user-attachments/assets/761720f0-852a-4033-849f-2fa0f557dcdb" />

### Final Assembly and Testing

#### Assemble and Check Clearances

- Once all components are installed, close up the calculator by pressing firmly on the sides.
- Ensure there is enough clearance for all components.

#### Power Up and Configure

- Boot up the calculator, go to the Home Screen, enable Host mode via the first switch, and then power the piggyback bia the second switch.

#### Open and Run Ti-GPT File

- Open the Ti-GPT file in the calculator's document folder.
- Ensure the ESP has successfully connected to your hotspot.

#### Testing and Usage

- Type into the textbox and hit enter.
- For short responses, they should appear immediately.
- For longer responses, you may need to hit enter again after a few seconds.

#### Troubleshooting

- If you encounter errors, hit CTRL + W to quit the program.
- Try power cycling your piggyback and checking your wiring for any issues.
- ALWAYS disconnect power and host/ID pin when not in use.
- Esp can get pretty hot in there under load or if on/idle too long.
- Please watch the step by step on Youtube and leave a comment if you are facing issues and I will do my best to respond.

### Disclaimer

I want to make it clear that this project is created for educational purposes and technological demonstration only. I do not condone academic dishonesty or the use of this project for cheating in any form.

The tools and methods demonstrated in this project should be used responsibly and ethically. Misuse of this technology for bypassing academic regulations or dishonest practices is strictly against the principles this project upholds.

Additionally, I do not endorse or support the use of my project by others for financial gain by others. This project is open-sourced to foster innovation and learning within the community, not for commercial exploitation.

Any reproduction or use of the project's content for profit without explicit permission is strictly prohibited. Please respect the spirit of collaboration and learning that this project is built upon.

### Refrences

- ChromaLock YouTube, GitHub  
  https://www.youtube.com/@ChromaLock

- ProfessorBoots YouTube, GitHub  
  https://github.com/ProfBoots/ChatGPT-On-Arduino

- CVSoft Cemetech, GitHub  
  https://github.com/CVSoft/nspire-usb-uart-shenanigans

- AndersJensen YouTube  
  https://www.youtube.com/watch?v=OB99E7Y1cMA&ab_channel=AndersJensen

- ti-nspire YouTube  
  https://www.youtube.com/@ti-nspire301

- CSab6482 Reddit  
  https://www.reddit.com/r/UsbCHardware/comments/y2dbkf/tinspire_cx_ii_cas_usbc_mod_v2/

### Thank You

Thank you so much for engaging with my project. While this repository captures the original implementation, the project is actively evolving and V2 will be released in a separate repository with a cleaner and more refined approach.

I appreciate all the feedback, curiosity, and experimentation this project has generated. Thank you for being part of it.
