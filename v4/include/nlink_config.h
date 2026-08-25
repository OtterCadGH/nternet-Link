// nternet-Link V4 — board configuration
// Pin maps and feature flags per hardware target.
#pragma once

#include <Arduino.h>

// ---------------------------------------------------------------------------
// UART link to the calculator (via CP2102/CP2102N USB bridge)
// ---------------------------------------------------------------------------
// nlink-cam (ESP32-S3-PICO-1) and the S3 dev/PCB targets share the S3 pin map.
#if defined(NLINK_BOARD_XIAO_S3) || defined(NLINK_BOARD_CUSTOM_PCB) \
    || defined(NLINK_BOARD_CAM_PICO)
  #define NLINK_UART_NUM   1
  #define NLINK_UART_RX    44   // from CP2102 TXD
  #define NLINK_UART_TX    43   // to CP2102 RXD
// nlink-lite (ESP32-C3-MINI-1): chat only, no camera, no SD.
#elif defined(NLINK_BOARD_LITE_C3)
  #define NLINK_UART_NUM   1
  #define NLINK_UART_RX    6    // from CP2102 TXD  (GPIO6)
  #define NLINK_UART_TX    7    // to   CP2102 RXD  (GPIO7)
#elif defined(NLINK_BOARD_XIAO_C3)
  #define NLINK_UART_NUM   0
  #define NLINK_UART_RX    -1   // default pins (D7/D6 on XIAO C3)
  #define NLINK_UART_TX    -1
#else
  #error "No board target defined (NLINK_BOARD_*)"
#endif

// Feature flags default on for camera-class boards; lite turns them off via
// build flags (NLINK_HAS_CAMERA=0, NLINK_HAS_SD=0).
#ifndef NLINK_HAS_SD
  #define NLINK_HAS_SD 1
#endif
#ifndef NLINK_STATUS_LED
  #if defined(NLINK_BOARD_LITE_C3)
    #define NLINK_STATUS_LED 8    // C3-MINI-1 common LED pin
  #else
    #define NLINK_STATUS_LED 1
  #endif
#endif

#define NLINK_UART_BAUD    115200

// ---------------------------------------------------------------------------
// Camera (OV5640 over DVP) — ESP32-S3 targets only
// ---------------------------------------------------------------------------
#if NLINK_HAS_CAMERA
  #define CAM_PIN_PWDN    -1
  #define CAM_PIN_RESET   -1
  #define CAM_PIN_XCLK    10
  #define CAM_PIN_SIOD    40
  #define CAM_PIN_SIOC    39
  #define CAM_PIN_Y9      48
  #define CAM_PIN_Y8      11
  #define CAM_PIN_Y7      12
  #define CAM_PIN_Y6      14
  #define CAM_PIN_Y5      16
  #define CAM_PIN_Y4      18
  #define CAM_PIN_Y3      17
  #define CAM_PIN_Y2      15
  #define CAM_PIN_VSYNC   38
  #define CAM_PIN_HREF    47
  #define CAM_PIN_PCLK    13
#endif

// ---------------------------------------------------------------------------
// microSD (SPI). XIAO ESP32S3 Sense expansion board: CS on GPIO21.
// Custom PCB uses the same SPI bus; adjust CS to your routing.
// ---------------------------------------------------------------------------
#if (defined(NLINK_BOARD_XIAO_S3) || defined(NLINK_BOARD_CUSTOM_PCB) \
     || defined(NLINK_BOARD_CAM_PICO)) && NLINK_HAS_SD
  #define NLINK_SD_CS   21
#endif

// ---------------------------------------------------------------------------
// Behaviour
// ---------------------------------------------------------------------------
#define NLINK_BUSY_TIMEOUT_MS     120000UL  // watchdog on long operations
#define NLINK_HTTP_TIMEOUT_MS     30000
#define NLINK_MAX_HISTORY         10        // chat turns kept in RAM
#define NLINK_CHUNK_PAYLOAD       360       // bytes of raw payload per frame
                                            // (b64 expands 4/3; keep frames < 512B)
