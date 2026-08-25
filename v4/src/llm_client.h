// Provider-agnostic LLM client (OpenAI-compatible chat/completions endpoints:
// Groq, OpenAI, OpenRouter, local llama.cpp/ollama gateways, etc.)
#pragma once

#include <Arduino.h>
#include <vector>
#include "provisioning.h"

namespace nlink {

struct ChatMessage {
  String role;
  String content;
};

class LlmClient {
 public:
  explicit LlmClient(Provisioning& prov) : prov_(prov) {}

  // Text question with conversation history. Returns reply or "ERR:..." text.
  String ask(const String& question);

  // Vision request on a JPEG (base64-encoded by caller).
  String askVision(const String& jpegB64, const String& prompt);

  void clearHistory();
  size_t historySize() const { return history_.size(); }

 private:
  Provisioning& prov_;
  std::vector<ChatMessage> history_;

  String post(const String& payload);
  void remember(const String& role, const String& content);
  String defaultSystemPrompt() const;
};

}  // namespace nlink
