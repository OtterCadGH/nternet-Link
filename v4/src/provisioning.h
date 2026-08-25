// Persistent configuration — NVS-backed. No secrets in source code.
#pragma once

#include <Arduino.h>
#include <Preferences.h>

namespace nlink {

struct Config {
  String wifiSsid;
  String wifiPass;
  String llmKey;       // API key
  String llmBase;      // e.g. https://api.groq.com/openai/v1
  String llmModel;     // text model id
  String llmVModel;    // vision model id
  String llmSys;       // system prompt override ("" = built-in default)
};

class Provisioning {
 public:
  void begin();
  Config& config() { return cfg_; }

  // Returns true if key was recognised and stored.
  bool set(const String& key, const String& value);
  // Returns value; secrets come back masked ("sk-…7f2a").
  String get(const String& key, bool masked = true);
  bool hasWifi() const { return cfg_.wifiSsid.length() > 0; }
  bool hasLlmKey() const { return cfg_.llmKey.length() > 0; }
  void clearAll();

 private:
  Preferences prefs_;
  Config cfg_;
  void load();
  void store(const char* k, const String& v);
};

}  // namespace nlink
