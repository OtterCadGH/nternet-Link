#include "provisioning.h"

namespace nlink {

static const char* NS = "nlink";

void Provisioning::begin() {
  prefs_.begin(NS, false);
  load();
}

void Provisioning::load() {
  cfg_.wifiSsid = prefs_.getString("wifi.ssid", "");
  cfg_.wifiPass = prefs_.getString("wifi.pass", "");
  cfg_.llmKey   = prefs_.getString("llm.key", "");
  cfg_.llmBase  = prefs_.getString("llm.base", "https://api.groq.com/openai/v1");
  cfg_.llmModel = prefs_.getString("llm.model", "llama-3.3-70b-versatile");
  cfg_.llmVModel = prefs_.getString("llm.vmodel",
                                    "meta-llama/llama-4-maverick-17b-128e-instruct");
  cfg_.llmSys   = prefs_.getString("llm.sys", "");
}

void Provisioning::store(const char* k, const String& v) {
  prefs_.putString(k, v);
}

bool Provisioning::set(const String& key, const String& value) {
  if      (key == "wifi.ssid")  cfg_.wifiSsid = value;
  else if (key == "wifi.pass")  cfg_.wifiPass = value;
  else if (key == "llm.key")    cfg_.llmKey = value;
  else if (key == "llm.base")   cfg_.llmBase = value;
  else if (key == "llm.model")  cfg_.llmModel = value;
  else if (key == "llm.vmodel") cfg_.llmVModel = value;
  else if (key == "llm.sys")    cfg_.llmSys = value;
  else return false;
  store(key.c_str(), value);
  return true;
}

static String mask(const String& v) {
  if (v.length() == 0) return "(unset)";
  if (v.length() <= 6) return "******";
  return v.substring(0, 3) + "..." + v.substring(v.length() - 4);
}

String Provisioning::get(const String& key, bool masked) {
  if (key == "wifi.ssid")  return cfg_.wifiSsid;
  if (key == "wifi.pass")  return masked ? mask(cfg_.wifiPass) : cfg_.wifiPass;
  if (key == "llm.key")    return masked ? mask(cfg_.llmKey) : cfg_.llmKey;
  if (key == "llm.base")   return cfg_.llmBase;
  if (key == "llm.model")  return cfg_.llmModel;
  if (key == "llm.vmodel") return cfg_.llmVModel;
  if (key == "llm.sys")    return cfg_.llmSys;
  return "(unknown key)";
}

void Provisioning::clearAll() {
  prefs_.clear();
  load();
}

}  // namespace nlink
