#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <HardwareSerial.h>

// Use the default UART (UART0) mapped to TX=D6 and RX=D7.
HardwareSerial MySerial0(0);

// Network credentials
const char* ssid = "network";
const char* password = "password";

// OpenAI API key
const char* apiKey = "chatgpt api key";
String apiUrl = "https://api.openai.com/v1/chat/completions";

WiFiClientSecure client;
HTTPClient http;

// Dynamic JSON document for conversation history
DynamicJsonDocument conversation(2048);

// String to accumulate UART input
String inString = "";

void setup() {
  // Initialize the default UART on TX = D6, RX = D7.
  MySerial0.begin(115200, SERIAL_8N1, -1, -1);
  
  // Connect to Wi-Fi without printing any connection status.
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
  }

  // Initialize secure client (insecure for testing only)
  client.setInsecure();

  // Set up the conversation JSON with the model and a system message.
  conversation["model"] = "gpt-3.5-turbo";
  JsonArray messages = conversation.createNestedArray("messages");
  JsonObject systemMsg = messages.createNestedObject();
  systemMsg["role"] = "system";
  systemMsg["content"] = "Be as concise as possible";
}

void loop() {
  // Read input from the default UART.
  while (MySerial0.available()) {
    char c = MySerial0.read();
    if (c != '\n') {
      inString += c;
    }
    if (c == '\n') {
      inString.trim();
      if (inString.length() > 0) {
        chatGptCall(inString);
      }
      inString = "";
    }
  }
  delay(1);
}

void chatGptCall(String userMessage) {
  // Add the user message to the conversation history.
  JsonArray messages = conversation["messages"].as<JsonArray>();
  JsonObject userObj = messages.createNestedObject();
  userObj["role"] = "user";
  userObj["content"] = userMessage;
  
  // Serialize the conversation JSON to a string.
  String jsonPayload;
  serializeJson(conversation, jsonPayload);
  
  http.begin(client, apiUrl);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", "Bearer " + String(apiKey));
  
  int httpResponseCode = http.POST(jsonPayload);
  if (httpResponseCode == 200) {
    String response = http.getString();
    DynamicJsonDocument respDoc(2048);
    DeserializationError error = deserializeJson(respDoc, response);
    if (!error) {
      String outputText = respDoc["choices"][0]["message"]["content"];
      MySerial0.println("Assistant: " + outputText);
      
      // Add the assistant's reply to the conversation history.
      JsonObject assistantObj = messages.createNestedObject();
      assistantObj["role"] = "assistant";
      assistantObj["content"] = outputText;
    } else {
      MySerial0.println("Error parsing JSON response");
    }
  } else {
    MySerial0.print("HTTP error code: ");
    MySerial0.println(httpResponseCode);
  }
  
  http.end(); // Free resources after the request
}
