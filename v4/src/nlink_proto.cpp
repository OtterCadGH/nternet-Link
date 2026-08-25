#include "nlink_proto.h"
#include "nlink_config.h"

namespace nlink {

// ---------------------------------------------------------------------------
// CRC16-CCITT (poly 0x1021, init 0xFFFF)
// ---------------------------------------------------------------------------
uint16_t crc16(const uint8_t* data, size_t len, uint16_t crc) {
  for (size_t i = 0; i < len; i++) {
    crc ^= (uint16_t)data[i] << 8;
    for (int b = 0; b < 8; b++)
      crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : (crc << 1);
  }
  return crc;
}

uint16_t crc16(const String& s, uint16_t crc) {
  return crc16((const uint8_t*)s.c_str(), s.length(), crc);
}

// ---------------------------------------------------------------------------
// Base64
// ---------------------------------------------------------------------------
static const char B64[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

String b64encode(const uint8_t* data, size_t len) {
  String out;
  out.reserve(((len + 2) / 3) * 4);
  for (size_t i = 0; i < len; i += 3) {
    uint32_t n = (uint32_t)data[i] << 16;
    if (i + 1 < len) n |= (uint32_t)data[i + 1] << 8;
    if (i + 2 < len) n |= data[i + 2];
    out += B64[(n >> 18) & 63];
    out += B64[(n >> 12) & 63];
    out += (i + 1 < len) ? B64[(n >> 6) & 63] : '=';
    out += (i + 2 < len) ? B64[n & 63] : '=';
  }
  return out;
}

String b64encode(const String& s) {
  return b64encode((const uint8_t*)s.c_str(), s.length());
}

static int8_t b64val(char c) {
  if (c >= 'A' && c <= 'Z') return c - 'A';
  if (c >= 'a' && c <= 'z') return c - 'a' + 26;
  if (c >= '0' && c <= '9') return c - '0' + 52;
  if (c == '+') return 62;
  if (c == '/') return 63;
  return -1;
}

String b64decode(const String& s) {
  String out;
  out.reserve((s.length() / 4) * 3);
  uint32_t buf = 0;
  int bits = 0;
  for (size_t i = 0; i < s.length(); i++) {
    int8_t v = b64val(s[i]);
    if (v < 0) continue;  // skip '=' and any stray chars
    buf = (buf << 6) | v;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      out += (char)((buf >> bits) & 0xFF);
    }
  }
  return out;
}

// ---------------------------------------------------------------------------
// Framing
// ---------------------------------------------------------------------------
static String hex2(uint8_t v) {
  char b[3];
  snprintf(b, sizeof(b), "%02X", v);
  return String(b);
}

static String hex4(uint16_t v) {
  char b[5];
  snprintf(b, sizeof(b), "%04X", v);
  return String(b);
}

String encodeFrame(char type, uint8_t seq, const String& payload) {
  String b64 = b64encode(payload);
  String body;
  body.reserve(b64.length() + 4);
  body += type;
  body += hex2(seq);
  body += '|';
  body += b64;
  String frame = "~1" + body + "|" + hex4(crc16(body)) + "\n";
  return frame;
}

// ---------------------------------------------------------------------------
// Parser
// ---------------------------------------------------------------------------
void Parser::feed(uint8_t byte) {
  if (byte == '\n' || byte == '\r') {
    if (line_.length() > 0) processLine();
    line_ = "";
    return;
  }
  line_ += (char)byte;
  if (line_.length() > 600) line_ = "";  // garbage guard; resync on next '\n'
}

void Parser::feed(const uint8_t* data, size_t len) {
  for (size_t i = 0; i < len; i++) feed(data[i]);
}

void Parser::processLine() {
  // Resync: frame may be preceded by noise — find the start marker.
  int start = line_.indexOf("~1");
  if (start < 0) return;
  String f = line_.substring(start + 2);

  // Layout: <type><seq2>|<b64>|<crc4>
  if (f.length() < 9) return;
  int lastBar = f.lastIndexOf('|');
  if (lastBar < 4 || (int)f.length() - lastBar != 5) return;

  String body = f.substring(0, lastBar);
  String crcStr = f.substring(lastBar + 1);
  uint16_t wantCrc = (uint16_t)strtoul(crcStr.c_str(), nullptr, 16);

  char type = body[0];
  uint8_t seq = (uint8_t)strtoul(body.substring(1, 3).c_str(), nullptr, 16);

  if (crc16(body) != wantCrc) {
    if (onBadFrame) onBadFrame(seq);
    return;
  }

  int bar = body.indexOf('|');
  String b64 = (bar >= 0) ? body.substring(bar + 1) : "";

  Frame frame;
  frame.type = type;
  frame.seq = seq;
  frame.payload = b64decode(b64);
  if (onFrame) onFrame(frame);
}

// ---------------------------------------------------------------------------
// Link
// ---------------------------------------------------------------------------
void Link::send(char type, const String& payload) {
  io_.print(encodeFrame(type, txSeq_++, payload));
  io_.flush();
}

void Link::sendChunkedBody(const String& body) {
  uint16_t bodyCrc = crc16(body);
  for (size_t i = 0; i < body.length(); i += NLINK_CHUNK_PAYLOAD) {
    String chunk = body.substring(i, min(body.length(), i + (size_t)NLINK_CHUNK_PAYLOAD));
    send(FT_DATA, chunk);
    delay(5);  // pacing — keeps calculator-side buffers comfortable
  }
  send(FT_END, String(body.length()) + "," + String(bodyCrc, HEX));
}

void Link::poll() {
  if (!parserWired_) {
    parser_.onFrame = [this](const Frame& f) { if (onFrame) onFrame(f); };
    parser_.onBadFrame = [this](uint8_t seq) { send(FT_NAK, String(seq)); };
    parserWired_ = true;
  }
  while (io_.available()) parser_.feed((uint8_t)io_.read());
}

}  // namespace nlink
