// nlink wire protocol v1 — framing, CRC16, base64. See docs/PROTOCOL.md.
#pragma once

#include <Arduino.h>
#include <functional>

namespace nlink {

// Frame types
enum FrameType : char {
  FT_HELLO      = 'H',
  FT_HELLO_ACK  = 'h',
  FT_COMMAND    = 'C',
  FT_ACK        = 'A',
  FT_NAK        = 'N',
  FT_STATUS     = 'S',
  FT_DATA       = 'D',
  FT_END        = 'E',
  FT_ERROR      = 'X',
};

struct Frame {
  char type;
  uint8_t seq;
  String payload;   // decoded (raw) payload
};

uint16_t crc16(const uint8_t* data, size_t len, uint16_t crc = 0xFFFF);
uint16_t crc16(const String& s, uint16_t crc = 0xFFFF);

String b64encode(const uint8_t* data, size_t len);
String b64encode(const String& s);
String b64decode(const String& s);

// Build a complete wire frame (includes trailing '\n').
String encodeFrame(char type, uint8_t seq, const String& payload);

// Incremental parser: feed bytes as they arrive; onFrame fires per valid
// frame; onBadFrame fires (with the seq if parseable) on CRC failure.
class Parser {
 public:
  std::function<void(const Frame&)> onFrame;
  std::function<void(uint8_t seq)> onBadFrame;

  void feed(uint8_t byte);
  void feed(const uint8_t* data, size_t len);

 private:
  String line_;
  void processLine();
};

// Sender helper bound to a Stream (the calculator UART).
class Link {
 public:
  explicit Link(Stream& io) : io_(io) {}

  void send(char type, const String& payload = "");
  void sendChunkedBody(const String& body);   // D…D + E with body CRC
  void poll();                                // pump parser from the stream

  std::function<void(const Frame&)> onFrame;

 private:
  Stream& io_;
  Parser parser_;
  uint8_t txSeq_ = 0;
  bool parserWired_ = false;
};

}  // namespace nlink
