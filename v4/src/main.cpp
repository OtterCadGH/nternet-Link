// nternet-Link V4 firmware — main dispatch.
// Calculator <-> device over framed nlink protocol (docs/PROTOCOL.md).

#include <Arduino.h>
#include <ArduinoJson.h>
#include <WiFi.h>

#include "camera_module.h"
#include "llm_client.h"
#include "nlink_config.h"
#include "nlink_proto.h"
#include "provisioning.h"
#include "storage.h"

using namespace nlink;

#if NLINK_UART_NUM == 1
HardwareSerial CalcSerial(1);
#else
HardwareSerial CalcSerial(0);
#endif

static Provisioning prov;
static LlmClient llm(prov);
static Camera camera;
static Storage storage;
static Link link_(CalcSerial);

static bool busy = false;
static unsigned long busyStart = 0;
static unsigned long lastHeartbeat = 0;

// ---------------------------------------------------------------------------
static bool wifiConnect(const String& ssid, const String& pass,
                        uint32_t timeoutMs = 15000) {
  WiFi.disconnect();
  delay(100);
  WiFi.begin(ssid.c_str(), pass.c_str());
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < timeoutMs)
    delay(250);
  return WiFi.status() == WL_CONNECTED;
}

static String wifiScan() {
  int n = WiFi.scanNetworks();
  String out = "NETWORKS ";
  if (n <= 0) {
    out += "none";
  } else {
    for (int i = 0; i < n && i < 12; i++) {
      if (i) out += "|";
      out += WiFi.SSID(i) + "(" + String(WiFi.RSSI(i)) + "dB)";
    }
  }
  WiFi.scanDelete();
  return out;
}

static String deviceInfoJson() {
  JsonDocument doc;
  doc["fw"] = NLINK_FW_VERSION;
  doc["heap"] = ESP.getFreeHeap();
  doc["camera"] = camera.available();
  doc["sd"] = storage.available();
  if (storage.available())
    doc["sd_free_mb"] = (uint32_t)(storage.freeBytes() / (1024 * 1024));
  doc["wifi"] = (WiFi.status() == WL_CONNECTED);
  if (WiFi.status() == WL_CONNECTED) doc["ip"] = WiFi.localIP().toString();
  doc["model"] = prov.config().llmModel;
  doc["vmodel"] = prov.config().llmVModel;
  doc["history"] = llm.historySize();
  String out;
  serializeJson(doc, out);
  return out;
}

// ---------------------------------------------------------------------------
static void handleCommand(const String& cmd) {
  // -- instant commands ------------------------------------------------------
  if (cmd == "PING") { link_.send(FT_STATUS, "PONG"); return; }
  if (cmd == "INFO") { link_.send(FT_ACK); link_.sendChunkedBody(deviceInfoJson()); return; }
  if (cmd == "CLEAR") { llm.clearHistory(); link_.send(FT_STATUS, "CLEARED"); return; }
  if (cmd == "RESET") { busy = false; link_.send(FT_STATUS, "OK"); return; }
  if (cmd == "REBOOT") {
    link_.send(FT_STATUS, "REBOOTING");
    CalcSerial.flush();
    delay(100);
    ESP.restart();
    return;
  }

  if (cmd.startsWith("CFG SET ")) {
    String rest = cmd.substring(8);
    int sp = rest.indexOf(' ');
    if (sp <= 0) { link_.send(FT_ERROR, "FORMAT CFG SET <key> <value>"); return; }
    String key = rest.substring(0, sp);
    String value = rest.substring(sp + 1);
    if (prov.set(key, value)) link_.send(FT_STATUS, "OK");
    else link_.send(FT_ERROR, "UNKNOWN_KEY " + key);
    return;
  }

  if (cmd.startsWith("CFG GET ")) {
    String key = cmd.substring(8);
    link_.send(FT_STATUS, "CFG " + key + "=" + prov.get(key));
    return;
  }

  if (cmd == "SCAN") {
    link_.send(FT_ACK);
    link_.send(FT_STATUS, wifiScan());
    return;
  }

  if (cmd.startsWith("WIFI ")) {
    String rest = cmd.substring(5);
    int tab = rest.indexOf('\t');
    if (tab <= 0) { link_.send(FT_ERROR, "FORMAT WIFI <ssid>\\t<pass>"); return; }
    String ssid = rest.substring(0, tab);
    String pass = rest.substring(tab + 1);
    link_.send(FT_STATUS, "CONNECTING");
    if (wifiConnect(ssid, pass)) {
      prov.set("wifi.ssid", ssid);   // remember for next boot
      prov.set("wifi.pass", pass);
      link_.send(FT_STATUS, "WIFI OK " + WiFi.localIP().toString());
    } else {
      link_.send(FT_STATUS, "WIFI FAIL");
    }
    return;
  }

  // -- long-running commands -------------------------------------------------
  if (busy) { link_.send(FT_ERROR, "BUSY"); return; }

  if (cmd == "SNAP" || cmd.startsWith("SNAP ")) {
    if (!camera.available()) { link_.send(FT_ERROR, "NO_CAMERA"); return; }
    if (WiFi.status() != WL_CONNECTED) { link_.send(FT_ERROR, "NO_WIFI"); return; }
    busy = true;
    busyStart = millis();
    link_.send(FT_ACK);
    link_.send(FT_STATUS, "PROCESSING");

    String prompt = cmd.startsWith("SNAP ") ? cmd.substring(5) : "";
    Jpeg jpeg;
    if (!camera.capture(jpeg)) {
      link_.send(FT_ERROR, "CAPTURE_FAILED");
    } else {
      // Photo hits the SD card first, so it's kept even if the API call fails.
      String saved = storage.savePhoto(jpeg.data, jpeg.len);
      if (saved.length()) link_.send(FT_STATUS, "SAVED " + saved);

      String b64 = b64encode(jpeg.data, jpeg.len);
      camera.release(jpeg);

      String reply = llm.askVision(b64, prompt);
      if (reply.startsWith("ERR:")) {
        link_.send(FT_ERROR, reply.substring(4));
      } else {
        storage.logChat("photo", saved.length() ? saved : "(not saved)");
        storage.logChat("assistant", reply);
        link_.sendChunkedBody(reply);
      }
    }
    busy = false;
    return;
  }

  if (cmd.startsWith("ASK ")) {
    if (WiFi.status() != WL_CONNECTED) { link_.send(FT_ERROR, "NO_WIFI"); return; }
    busy = true;
    busyStart = millis();
    link_.send(FT_ACK);
    link_.send(FT_STATUS, "PROCESSING");

    String question = cmd.substring(4);
    String reply = llm.ask(question);
    if (reply.startsWith("ERR:")) {
      link_.send(FT_ERROR, reply.substring(4));
    } else {
      storage.logChat("user", question);
      storage.logChat("assistant", reply);
      link_.sendChunkedBody(reply);
    }
    busy = false;
    return;
  }

  // -- SD card commands ------------------------------------------------------
  if (cmd.startsWith("LS")) {
    if (!storage.available()) { link_.send(FT_ERROR, "NO_SD"); return; }
    String dir = cmd.length() > 3 ? cmd.substring(3) : "/";
    link_.send(FT_ACK);
    link_.sendChunkedBody(storage.listDir(dir));
    return;
  }

  if (cmd.startsWith("GET ")) {
    if (!storage.available()) { link_.send(FT_ERROR, "NO_SD"); return; }
    String contents = storage.readFile(cmd.substring(4));
    if (contents == "") { link_.send(FT_ERROR, "NOT_FOUND"); return; }
    link_.send(FT_ACK);
    link_.sendChunkedBody(contents);
    return;
  }

  if (cmd.startsWith("PUT ")) {
    if (!storage.available()) { link_.send(FT_ERROR, "NO_SD"); return; }
    String rest = cmd.substring(4);
    int tab = rest.indexOf('\t');
    if (tab <= 0) { link_.send(FT_ERROR, "FORMAT PUT <name>\\t<contents>"); return; }
    if (storage.saveFile(rest.substring(0, tab), rest.substring(tab + 1)))
      link_.send(FT_STATUS, "OK");
    else
      link_.send(FT_ERROR, "WRITE_FAILED");
    return;
  }

  if (cmd == "NEWCHAT") {
    llm.clearHistory();
    storage.newChatSession();
    link_.send(FT_STATUS, "CLEARED");
    return;
  }

  link_.send(FT_ERROR, "UNKNOWN_CMD");
}

static void handleFrame(const Frame& f) {
  switch (f.type) {
    case FT_HELLO: {
      String caps = "wifi";
      if (camera.available()) caps += ",cam";
      if (storage.available()) caps += ",sd";
      link_.send(FT_HELLO_ACK, String("NLINK,") + NLINK_FW_VERSION + "," + caps);
      break;
    }
    case FT_COMMAND:
      handleCommand(f.payload);
      break;
    case FT_NAK:
      // Peer saw a corrupt frame. Long bodies are re-requested at command
      // level by the calculator, so nothing to do here beyond logging.
      Serial.printf("[nlink] NAK for seq %s\n", f.payload.c_str());
      break;
    default:
      break;
  }
}

// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  CalcSerial.begin(NLINK_UART_BAUD, SERIAL_8N1, NLINK_UART_RX, NLINK_UART_TX);
  delay(500);

  Serial.println("\n=== nternet-Link V4 (" NLINK_FW_VERSION ") ===");

  prov.begin();

#if NLINK_HAS_CAMERA
  Serial.println(camera.begin() ? "Camera OK" : "Camera unavailable");
#endif

  Serial.println(storage.begin() ? "SD card OK" : "No SD card");

  WiFi.mode(WIFI_STA);
  if (prov.hasWifi()) {
    Serial.printf("Auto-connecting to %s...\n", prov.config().wifiSsid.c_str());
    if (wifiConnect(prov.config().wifiSsid, prov.config().wifiPass))
      Serial.println("WiFi OK: " + WiFi.localIP().toString());
    else
      Serial.println("WiFi auto-connect failed (set up from calculator)");
  }

  link_.onFrame = handleFrame;
  link_.send(FT_STATUS, WiFi.status() == WL_CONNECTED
                            ? "WIFI OK " + WiFi.localIP().toString()
                            : "WIFI NONE");
  Serial.println("Ready.");
}

void loop() {
  link_.poll();

  // Watchdog: never stay busy forever.
  if (busy && millis() - busyStart > NLINK_BUSY_TIMEOUT_MS) {
    busy = false;
    link_.send(FT_ERROR, "TIMEOUT");
  }

  // Heartbeat + WiFi self-heal.
  if (millis() - lastHeartbeat > 30000) {
    lastHeartbeat = millis();
    if (prov.hasWifi() && WiFi.status() != WL_CONNECTED) WiFi.reconnect();
  }

  // USB serial debug passthrough: type protocol commands directly.
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length()) handleCommand(cmd);
  }

  delay(1);
}
