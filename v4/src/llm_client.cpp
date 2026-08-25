#include "llm_client.h"

#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>

#include "nlink_config.h"

namespace nlink {

String LlmClient::defaultSystemPrompt() const {
  return
      "You are a STEM tutor rendered on a 320x240 calculator screen. "
      "PLAIN TEXT only: no LaTeX, no markdown. Use x^2 for powers, sqrt() "
      "for roots, a/b for fractions, d/dx and integral(f dx) for calculus, "
      "spell out greek letters. Align matrix columns with spaces. Number "
      "your steps. Be concise.";
}

void LlmClient::remember(const String& role, const String& content) {
  history_.push_back({role, content});
  while (history_.size() > NLINK_MAX_HISTORY)
    history_.erase(history_.begin());
}

void LlmClient::clearHistory() { history_.clear(); }

String LlmClient::post(const String& payload) {
  if (!prov_.hasLlmKey()) return "ERR:NO_API_KEY (set with CFG SET llm.key ...)";

  HTTPClient http;
  http.begin(prov_.config().llmBase + "/chat/completions");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", "Bearer " + prov_.config().llmKey);
  http.setTimeout(NLINK_HTTP_TIMEOUT_MS);

  int code = http.POST(payload);
  String result;

  if (code == 200) {
    // Filter: only keep the fields we need — avoids a large scratch doc.
    JsonDocument filter;
    filter["choices"][0]["message"]["content"] = true;
    JsonDocument doc;
    DeserializationError err =
        deserializeJson(doc, http.getString(), DeserializationOption::Filter(filter));
    if (err) {
      result = "ERR:JSON " + String(err.c_str());
    } else {
      result = doc["choices"][0]["message"]["content"].as<String>();
    }
  } else {
    String body = http.getString();
    result = "ERR:HTTP " + String(code);
    if (body.length()) result += " " + body.substring(0, 160);
  }

  http.end();
  return result;
}

String LlmClient::ask(const String& question) {
  JsonDocument doc;
  doc["model"] = prov_.config().llmModel;
  doc["max_tokens"] = 4096;
  JsonArray messages = doc["messages"].to<JsonArray>();

  JsonObject sys = messages.add<JsonObject>();
  sys["role"] = "system";
  sys["content"] = prov_.config().llmSys.length() ? prov_.config().llmSys
                                                  : defaultSystemPrompt();

  for (auto& m : history_) {
    JsonObject o = messages.add<JsonObject>();
    o["role"] = m.role;
    o["content"] = m.content;
  }
  JsonObject user = messages.add<JsonObject>();
  user["role"] = "user";
  user["content"] = question;

  String payload;
  serializeJson(doc, payload);
  String reply = post(payload);

  if (!reply.startsWith("ERR:")) {
    remember("user", question);
    remember("assistant", reply);
  }
  return reply;
}

String LlmClient::askVision(const String& jpegB64, const String& prompt) {
  JsonDocument doc;
  doc["model"] = prov_.config().llmVModel;
  doc["max_tokens"] = 4096;
  JsonArray messages = doc["messages"].to<JsonArray>();
  JsonObject user = messages.add<JsonObject>();
  user["role"] = "user";
  JsonArray content = user["content"].to<JsonArray>();

  JsonObject img = content.add<JsonObject>();
  img["type"] = "image_url";
  img["image_url"]["url"] = "data:image/jpeg;base64," + jpegB64;

  JsonObject txt = content.add<JsonObject>();
  txt["type"] = "text";
  txt["text"] = prompt.length()
                    ? prompt
                    : "Describe and work through what is in this image. " +
                          defaultSystemPrompt();

  String payload;
  serializeJson(doc, payload);
  String reply = post(payload);

  if (!reply.startsWith("ERR:")) {
    remember("user", "[photo]");
    remember("assistant", reply);
  }
  return reply;
}

}  // namespace nlink
