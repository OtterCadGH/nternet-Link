#include "esp_camera.h"
#include <WiFi.h>
#include <WiFiManager.h>
#include <Preferences.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "base64.h"
#include "ESP32_OV5640_AF.h"
#include <vector>
#include <WebServer.h>

WebServer server(80);
WiFiManager wifiManager;
Preferences preferences;

// https://console.groq.com/keys
const char* groqApiKey = "YOUR_GROQ_API_KEY_HERE";

struct Message {
  String role;
  String content;
};
std::vector<Message> conversationHistory;
const int MAX_HISTORY = 10;

volatile bool isBusy = false;
unsigned long busyStartTime = 0;
const unsigned long BUSY_TIMEOUT = 120000;

// Camera pin definitions (ESP32-S3 + OV5640)
#define PWDN_GPIO_NUM     -1
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM     10
#define SIOD_GPIO_NUM     40
#define SIOC_GPIO_NUM     39
#define Y9_GPIO_NUM       48
#define Y8_GPIO_NUM       11
#define Y7_GPIO_NUM       12
#define Y6_GPIO_NUM       14
#define Y5_GPIO_NUM       16
#define Y4_GPIO_NUM       18
#define Y3_GPIO_NUM       17
#define Y2_GPIO_NUM       15
#define VSYNC_GPIO_NUM    38
#define HREF_GPIO_NUM     47
#define PCLK_GPIO_NUM     13

OV5640 ov5640 = OV5640();
bool afInitialized = false;

bool triggerAutofocus() {
  if (!afInitialized) {
    Serial.println("AF not initialized");
    return false;
  }

  Serial.println("Focusing...");
  sensor_t *s = esp_camera_sensor_get();

  s->set_reg(s, 0x3022, 0xFF, 0x08);
  delay(10);
  s->set_reg(s, 0x3022, 0xFF, 0x03);
  s->set_reg(s, 0x3023, 0xFF, 0x01);

  unsigned long start = millis();
  while ((millis() - start) < 3000) {
    int status = ov5640.getFWStatus();
    if (status == FW_STATUS_S_FOCUSED) {
      Serial.println("Focus OK");
      return true;
    }
    if (status == FW_STATUS_S_STARTUP) {
      delay(50);
      continue;
    }
    delay(50);
  }
  Serial.println("Focus timeout");
  return false;
}

void handleRoot() {
  String html = "<!DOCTYPE html><html><head>";
  html += "<title>ESP32 Camera</title>";
  html += "<meta name='viewport' content='width=device-width,initial-scale=1'>";
  html += "<style>body{font-family:Arial;text-align:center;background:#1a1a1a;color:white;margin:10px;}";
  html += "img{max-width:100%;max-height:70vh;border:2px solid #444;border-radius:8px;}";
  html += "button{padding:12px 24px;font-size:16px;margin:8px;cursor:pointer;background:#4CAF50;color:white;border:none;border-radius:5px;}";
  html += "button:hover{background:#45a049;}";
  html += ".danger{background:#f44336;}.danger:hover{background:#d32f2f;}";
  html += ".info{font-size:12px;color:#888;margin-top:15px;}</style></head><body>";
  html += "<h2>ESP32-S3 Camera</h2>";
  html += "<div><img src='/stream' id='stream'></div>";
  html += "<div><button onclick='focus()'>AUTOFOCUS</button>";
  html += "<button onclick='toggleMode()' id='modeBtn'>Switch to Snapshot</button></div>";
  html += "<p id='status'>Live stream active</p>";
  html += "<div class='info'>WiFi: " + WiFi.SSID() + " | IP: " + WiFi.localIP().toString() + "</div>";
  html += "<div><button class='danger' onclick='resetWifi()'>Change WiFi</button></div>";
  html += "<script>";
  html += "var streaming=true;var interval=null;";
  html += "function focus(){document.getElementById('status').innerText='Focusing...';fetch('/focus').then(r=>r.text()).then(t=>document.getElementById('status').innerText=t);}";
  html += "function resetWifi(){if(confirm('Reset WiFi?')){window.location='/resetwifi';}}";
  html += "function toggleMode(){";
  html += "streaming=!streaming;var img=document.getElementById('stream');var btn=document.getElementById('modeBtn');";
  html += "if(streaming){if(interval)clearInterval(interval);img.src='/stream';btn.innerText='Switch to Snapshot';document.getElementById('status').innerText='Live stream active';}";
  html += "else{img.src='/capture?'+Date.now();btn.innerText='Switch to Stream';document.getElementById('status').innerText='Snapshot mode (auto-refresh)';";
  html += "interval=setInterval(function(){img.src='/capture?'+Date.now();},100);}}";
  html += "</script></body></html>";
  server.send(200, "text/html", html);
}

void handleCapture() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    server.send(500, "text/plain", "Capture failed");
    return;
  }
  server.sendHeader("Content-Type", "image/jpeg");
  server.sendHeader("Content-Length", String(fb->len));
  server.send(200, "image/jpeg", "");
  WiFiClient client = server.client();
  client.write(fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

void handleStream() {
  WiFiClient client = server.client();

  String response = "HTTP/1.1 200 OK\r\n";
  response += "Content-Type: multipart/x-mixed-replace; boundary=frame\r\n";
  response += "Access-Control-Allow-Origin: *\r\n";
  response += "Cache-Control: no-cache, no-store, must-revalidate\r\n";
  response += "\r\n";
  client.print(response);

  unsigned long streamStart = millis();
  const unsigned long STREAM_TIMEOUT = 30000;

  while (true) {
    if (millis() - streamStart > STREAM_TIMEOUT) {
      Serial.println("Stream timeout");
      break;
    }

    if (!client.connected()) break;

    // End stream early if Nspire is sending a command
    if (Serial1.available() > 0) {
      Serial.println("Serial data waiting, ending stream");
      break;
    }

    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Stream capture failed");
      delay(100);
      continue;
    }

    client.printf("--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n", fb->len);

    size_t written = 0;
    size_t toWrite = fb->len;
    uint8_t *buf = fb->buf;

    while (written < toWrite) {
      size_t chunk = min((size_t)4096, toWrite - written);
      size_t sent = client.write(buf + written, chunk);
      if (sent == 0) break;
      written += sent;
    }

    client.print("\r\n");
    esp_camera_fb_return(fb);

    if (written < toWrite) break;
    delay(10);
  }
}

void handleFocus() {
  if (triggerAutofocus()) {
    server.send(200, "text/plain", "Focus OK!");
  } else {
    server.send(200, "text/plain", "Focus failed or timeout");
  }
}

void handleResetWifi() {
  server.send(200, "text/html", "<html><body><h1>WiFi Reset</h1><p>WiFi settings cleared. Device will restart and create 'AI-Camera-Setup' hotspot.</p></body></html>");
  delay(1000);
  wifiManager.resetSettings();
  ESP.restart();
}

void flushCameraBuffers() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (fb) esp_camera_fb_return(fb);
}

String scanNetworks() {
  Serial.println("Scanning WiFi networks...");
  flushCameraBuffers();

  int n = WiFi.scanNetworks();
  flushCameraBuffers();

  String result = "NETWORKS:";

  if (n == 0) {
    result += "None found";
  } else {
    for (int i = 0; i < n && i < 10; i++) {
      if (i > 0) result += "|";
      result += WiFi.SSID(i);
      result += "(" + String(WiFi.RSSI(i)) + "dB)";
    }
  }

  WiFi.scanDelete();
  return result;
}

bool connectToWiFi(String ssid, String password) {
  Serial.println("Connecting to: " + ssid);
  flushCameraBuffers();

  WiFi.disconnect();
  delay(100);
  WiFi.begin(ssid.c_str(), password.c_str());

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    if (attempts % 5 == 0) flushCameraBuffers();
    attempts++;
  }
  Serial.println();
  flushCameraBuffers();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("Connected! IP: " + WiFi.localIP().toString());
    server.begin();
    Serial.println("Web server started at http://" + WiFi.localIP().toString());
    return true;
  }

  Serial.println("Connection failed");
  return false;
}

String sendToVisionAPI(String &base64Image) {
  HTTPClient http;
  http.begin("https://api.groq.com/openai/v1/chat/completions");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", "Bearer " + String(groqApiKey));
  http.setTimeout(30000);

  String payload = "{\"model\":\"meta-llama/llama-4-maverick-17b-128e-instruct\",";
  payload += "\"max_tokens\":4096,";
  payload += "\"messages\":[{\"role\":\"user\",\"content\":[";
  payload += "{\"type\":\"image_url\",\"image_url\":{\"url\":\"data:image/jpeg;base64," + base64Image + "\"}},";
  payload += "{\"type\":\"text\",\"text\":\"Read this image and solve the math problem. Output in PLAIN TEXT only. No LaTeX, no markdown. Use x^2 for powers, sqrt() for roots, a/b for fractions. Show steps. Be concise.\"}";
  payload += "]}]}";

  Serial.println("API POST starting...");
  int httpCode = http.POST(payload);
  Serial.printf("API response code: %d\n", httpCode);

  String result;

  if (httpCode == 200) {
    String response = http.getString();
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, response);
    if (err) {
      result = "JSON Error: " + String(err.c_str());
    } else {
      result = doc["choices"][0]["message"]["content"].as<String>();
      addToHistory("user", "[Photo of math problem]");
      addToHistory("assistant", result);
    }
  } else {
    String errorBody = http.getString();
    Serial.println("API Error body: " + errorBody.substring(0, 200));
    result = "API Error " + String(httpCode);
  }

  http.end();
  return result;
}

void addToHistory(String role, String content) {
  Message msg;
  msg.role = role;
  msg.content = content;
  conversationHistory.push_back(msg);

  while (conversationHistory.size() > MAX_HISTORY) {
    conversationHistory.erase(conversationHistory.begin());
  }
}

void clearHistory() {
  conversationHistory.clear();
  Serial.println("Conversation cleared");
}

String escapeJson(String text) {
  text.replace("\\", "\\\\");
  text.replace("\"", "\\\"");
  text.replace("\n", "\\n");
  text.replace("\r", "\\r");
  text.replace("\t", "\\t");
  return text;
}

String sendTextQuery(String &question) {
  HTTPClient http;
  http.begin("https://api.groq.com/openai/v1/chat/completions");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", "Bearer " + String(groqApiKey));
  http.setTimeout(30000);

  String payload = "{\"model\":\"llama-3.3-70b-versatile\",";
  payload += "\"max_tokens\":4096,";
  payload += "\"messages\":[";

  // System prompt: plain text formatting rules for calculator display
  payload += "{\"role\":\"system\",\"content\":\"You are a math/data science tutor for a calculator. FORMAT RULES: "
             "1) PLAIN TEXT only - no LaTeX, markdown, or special symbols. "
             "2) MATRICES: Align columns with spaces so entries line up vertically. Each row on its own line. "
             "3) FRACTIONS: a/b format (1/2, -3/4, 11/12). "
             "4) POWERS: x^2, e^x. ROOTS: sqrt(x), cbrt(x). "
             "5) GREEK: spell out (alpha, beta, sigma, mu, theta, pi, lambda). "
             "6) STATS: x-bar=mean, s=std dev, P(X)=probability, E[X]=expected value, Var(X)=variance. "
             "7) CALCULUS: d/dx, integral(f dx), lim(x->a), sum(i=1 to n). "
             "8) VECTORS: <a,b,c> or [a,b,c]. SETS: {1,2,3}, union, intersect. "
             "9) LINEAR ALGEBRA: det(A), A^T=transpose, A^(-1)=inverse, rank(A), null(A). "
             "Number your steps. Be concise - small screen display.\"}";

  for (int i = 0; i < conversationHistory.size(); i++) {
    payload += ",{\"role\":\"" + conversationHistory[i].role + "\",";
    payload += "\"content\":\"" + escapeJson(conversationHistory[i].content) + "\"}";
  }

  String escapedQuestion = escapeJson(question);
  payload += ",{\"role\":\"user\",\"content\":\"" + escapedQuestion + "\"}";
  payload += "]}";

  Serial.println("Sending text query with " + String(conversationHistory.size()) + " history messages...");
  int httpCode = http.POST(payload);
  String result;

  if (httpCode == 200) {
    String response = http.getString();
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, response);
    if (err) {
      result = "JSON Error: " + String(err.c_str());
    } else {
      result = doc["choices"][0]["message"]["content"].as<String>();
      addToHistory("user", question);
      addToHistory("assistant", result);
    }
  } else {
    result = "HTTP Error " + String(httpCode) + ": " + http.getString();
  }

  http.end();
  return result;
}

String doSnap() {
  Serial.println("\n=== SNAP START ===");
  unsigned long startTime = millis();

  flushCameraBuffers();
  triggerAutofocus();
  delay(200);
  flushCameraBuffers();

  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("ERROR: Capture failed!");
    return "ERROR: Camera capture failed";
  }
  Serial.printf("Captured: %dx%d, %d bytes\n", fb->width, fb->height, fb->len);

  String base64Image = base64::encode(fb->buf, fb->len);
  Serial.printf("Base64: %d chars\n", base64Image.length());
  esp_camera_fb_return(fb);

  String result = sendToVisionAPI(base64Image);
  Serial.printf("Done: %d chars in %lu ms\n", result.length(), millis() - startTime);

  Serial.println("=== SNAP END ===\n");
  return result;
}

void setup() {
  Serial.begin(115200);
  Serial1.begin(115200, SERIAL_8N1, 44, 43); // UART to Nspire via CP2102
  delay(2000);
  Serial.println("\n=== AI Calculator ===\n");

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.frame_size = FRAMESIZE_VGA;
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_LATEST;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 8;
  config.fb_count = 2;

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("Camera init failed!");
    return;
  }
  Serial.println("Camera OK");

  sensor_t *s = esp_camera_sensor_get();
  if (s->id.PID == OV5640_PID) {
    Serial.println("OV5640 detected");

    s->set_brightness(s, 1);
    s->set_contrast(s, 1);
    s->set_saturation(s, 0);
    s->set_sharpness(s, 2);
    s->set_whitebal(s, 1);
    s->set_awb_gain(s, 1);
    s->set_exposure_ctrl(s, 1);
    s->set_aec2(s, 1);
    s->set_gain_ctrl(s, 1);
    s->set_hmirror(s, 1);
    s->set_vflip(s, 0);

    ov5640.start(s);
    if (ov5640.focusInit() == 0) {
      Serial.println("AF firmware loaded");
      afInitialized = true;
    } else {
      Serial.println("AF firmware failed");
    }
  } else {
    Serial.println("Not OV5640, no AF support");
  }

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);

  server.on("/", handleRoot);
  server.on("/capture", handleCapture);
  server.on("/stream", handleStream);
  server.on("/focus", handleFocus);
  server.on("/resetwifi", handleResetWifi);

  Serial.println("\nReady. Commands: PING, SNAP, FOCUS, ASK:<text>, CLEAR, SCAN, WIFI:ssid:pass");

  delay(500);
  Serial1.println("WIFI:NONE");
  Serial1.println("READY");
}

unsigned long lastHeartbeat = 0;

void loop() {
  server.handleClient();

  // Heartbeat every 30s, auto-reconnect WiFi if lost
  if (millis() - lastHeartbeat > 30000) {
    lastHeartbeat = millis();
    Serial.printf("[Status] Heap: %d, WiFi: %s\n",
                  ESP.getFreeHeap(),
                  WiFi.status() == WL_CONNECTED ? "OK" : "DOWN");

    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("WiFi lost! Reconnecting...");
      WiFi.reconnect();
    }
  }

  // Watchdog: auto-clear busy flag after timeout
  if (isBusy && (millis() - busyStartTime > BUSY_TIMEOUT)) {
    Serial.println("[Watchdog] Busy timeout, auto-clearing");
    isBusy = false;
    Serial1.println("ERR:TIMEOUT");
    Serial1.flush();
  }

  // USB Serial commands (debug interface)
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "PING") {
      Serial.println("PONG");
    }
    else if (cmd == "SNAP") {
      String result = doSnap();
      Serial.println(result);
    }
    else if (cmd == "FOCUS") {
      triggerAutofocus();
    }
    else if (cmd.startsWith("ASK:")) {
      String question = cmd.substring(4);
      String result = sendTextQuery(question);
      Serial.println(result);
    }
    else if (cmd == "CLEAR") {
      clearHistory();
      Serial.println("OK:CLEARED");
    }
    else if (cmd == "RESETWIFI") {
      Serial.println("Resetting WiFi settings...");
      wifiManager.resetSettings();
      Serial.println("Restarting...");
      delay(1000);
      ESP.restart();
    }
  }

  // Nspire Serial commands (main interface)
  if (Serial1.available()) {
    int avail = Serial1.available();
    String cmd = Serial1.readStringUntil('\n');
    cmd.trim();
    Serial.printf("Nspire (%d bytes): [%s]\n", avail, cmd.c_str());

    if (cmd == "PING") {
      Serial1.println("PONG");
    }
    else if (cmd == "SNAP") {
      if (isBusy) {
        Serial1.println("ERR:BUSY");
        return;
      }
      isBusy = true;
      busyStartTime = millis();

      Serial.printf("SNAP received, heap: %d\n", ESP.getFreeHeap());

      Serial1.println("OK:PROCESSING");
      Serial1.flush();
      delay(50);

      String result = doSnap();
      Serial.printf("Result: %d chars, heap: %d\n", result.length(), ESP.getFreeHeap());

      // Send length prefix so Nspire knows how much to expect
      Serial1.println("LEN:" + String(result.length()));
      Serial1.flush();
      delay(20);

      Serial1.print("RESULT:");
      Serial1.flush();

      // Send in 512-byte chunks to avoid buffer overflow
      int chunkSize = 512;
      for (int i = 0; i < result.length(); i += chunkSize) {
        String chunk = result.substring(i, min((int)result.length(), i + chunkSize));
        Serial1.print(chunk);
        Serial1.flush();
        delay(5);
      }

      Serial1.println();
      Serial1.flush();
      delay(10);
      Serial1.println(">>>END<<<");
      Serial1.flush();
      delay(20);

      result = "";
      Serial.printf("SNAP complete, heap: %d\n", ESP.getFreeHeap());
      isBusy = false;
    }
    else if (cmd == "FOCUS") {
      if (triggerAutofocus()) {
        Serial1.println("OK:FOCUSED");
      } else {
        Serial1.println("ERR:FOCUS_FAILED");
      }
    }
    else if (cmd.startsWith("ASK:")) {
      if (isBusy) {
        Serial1.println("ERR:BUSY");
        return;
      }
      isBusy = true;
      busyStartTime = millis();
      Serial1.println("OK:PROCESSING");
      Serial1.flush();
      delay(50);

      String question = cmd.substring(4);
      Serial.println("ASK: " + question);
      String result = sendTextQuery(question);
      Serial.printf("Answer: %d chars\n", result.length());

      Serial1.println("LEN:" + String(result.length()));
      Serial1.flush();
      delay(20);

      Serial1.print("RESULT:");
      Serial1.flush();
      int chunkSize = 512;
      for (int i = 0; i < result.length(); i += chunkSize) {
        String chunk = result.substring(i, min((int)result.length(), i + chunkSize));
        Serial1.print(chunk);
        Serial1.flush();
        delay(5);
      }
      Serial1.println();
      Serial1.flush();
      delay(10);
      Serial1.println(">>>END<<<");
      Serial1.flush();

      Serial.println("ASK complete");
      isBusy = false;
    }
    else if (cmd == "CLEAR") {
      clearHistory();
      Serial1.println("OK:CLEARED");
    }
    else if (cmd == "RESET") {
      Serial.println("RESET received, clearing busy flag");
      isBusy = false;
      Serial1.println("OK:RESET");
      Serial1.flush();
    }
    else if (cmd == "RESTART") {
      Serial.println("Soft restart requested");
      isBusy = false;
      conversationHistory.clear();
      flushCameraBuffers();

      if (afInitialized) {
        triggerAutofocus();
      }

      Serial.printf("Soft restart complete, heap: %d\n", ESP.getFreeHeap());
      Serial1.println("OK:RESTARTED");
      Serial1.flush();
    }
    else if (cmd == "HARDRESET") {
      Serial.println("HARD RESET, full reboot");
      Serial1.println("OK:REBOOTING");
      Serial1.flush();
      delay(100);
      ESP.restart();
    }
    else if (cmd == "SCAN") {
      Serial1.println("OK:SCANNING");
      Serial1.flush();
      String networks = scanNetworks();
      Serial.println("Scan result: " + networks);
      Serial1.println(networks);
      Serial1.flush();
      delay(50);
    }
    else if (cmd.startsWith("WIFI:")) {
      String params = cmd.substring(5);
      int colonPos = params.indexOf(':');
      if (colonPos > 0) {
        String ssid = params.substring(0, colonPos);
        String password = params.substring(colonPos + 1);
        Serial1.println("OK:CONNECTING");
        Serial1.flush();
        if (connectToWiFi(ssid, password)) {
          Serial1.println("WIFI:OK:" + WiFi.localIP().toString());
          Serial1.flush();
        } else {
          Serial1.println("WIFI:FAIL");
          Serial1.flush();
        }
      } else {
        Serial1.println("ERR:FORMAT (use WIFI:ssid:password)");
      }
    }
    else if (cmd == "IP") {
      if (WiFi.status() == WL_CONNECTED) {
        Serial1.println("IP:" + WiFi.localIP().toString());
      } else {
        Serial1.println("IP:NOT_CONNECTED");
      }
    }
  }
}
