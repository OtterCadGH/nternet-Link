// Host-side test for the nlink protocol codec.
// Build: g++ -std=c++17 -I test/fakeinc test/test_proto.cpp -o /tmp/test_proto
#include "../src/nlink_proto.h"
#include "../src/nlink_proto.cpp"

#include <cassert>
#include <iostream>
#include <vector>

using namespace nlink;

int failures = 0;
#define CHECK(cond, msg)                                        \
  do {                                                          \
    if (!(cond)) {                                              \
      std::cout << "FAIL: " << msg << "\n";                     \
      failures++;                                               \
    } else {                                                    \
      std::cout << "ok:   " << msg << "\n";                     \
    }                                                           \
  } while (0)

int main() {
  // CRC16-CCITT known-answer test: "123456789" -> 0x29B1
  CHECK(crc16(String("123456789")) == 0x29B1, "crc16 known answer 0x29B1");

  // Base64 round trip incl. binary bytes
  {
    std::string raw;
    for (int i = 0; i < 256; i++) raw += (char)i;
    String enc = b64encode((const uint8_t*)raw.data(), raw.size());
    String dec = b64decode(enc);
    CHECK(dec.std_str() == raw, "base64 round-trips all 256 byte values");
  }
  CHECK(b64encode(String("PING")) == "UElORw==", "base64 of PING matches reference");

  // Frame round trip
  {
    Parser p;
    Frame got{};
    bool fired = false;
    p.onFrame = [&](const Frame& f) { got = f; fired = true; };
    String wire = encodeFrame(FT_COMMAND, 7, "ASK what is 2+2?");
    for (size_t i = 0; i < wire.length(); i++) p.feed(wire[i]);
    CHECK(fired, "frame parses");
    CHECK(got.type == 'C' && got.seq == 7, "type+seq survive");
    CHECK(got.payload == "ASK what is 2+2?", "payload survives");
  }

  // Corrupt frame -> onBadFrame, not onFrame
  {
    Parser p;
    bool bad = false, good = false;
    p.onFrame = [&](const Frame&) { good = true; };
    p.onBadFrame = [&](uint8_t) { bad = true; };
    std::string wire = encodeFrame(FT_COMMAND, 3, "PING").std_str();
    wire[6] = (wire[6] == 'A') ? 'B' : 'A';  // flip a payload char
    for (char c : wire) p.feed((uint8_t)c);
    CHECK(bad && !good, "corrupt frame rejected via CRC");
  }

  // Noise resync: garbage + boot spam around a valid frame
  {
    Parser p;
    int frames = 0;
    p.onFrame = [&](const Frame&) { frames++; };
    std::string wire = "ets Jul 29 2019 12:21:46\r\nnoise~garbage\n" +
                       encodeFrame(FT_STATUS, 1, "PONG").std_str() +
                       "more noise\n";
    for (char c : wire) p.feed((uint8_t)c);
    CHECK(frames == 1, "parser resyncs through boot noise");
  }

  // Chunked body: 1000-byte body -> D frames + E frame, reassembles + CRC ok
  {
    Stream io;
    Link link(io);
    std::string body;
    for (int i = 0; i < 1000; i++) body += (char)('a' + i % 26);
    link.sendChunkedBody(String(body));

    Parser p;
    std::string rebuilt;
    long total = -1;
    uint16_t bodyCrc = 0;
    p.onFrame = [&](const Frame& f) {
      if (f.type == FT_DATA) rebuilt += f.payload.std_str();
      if (f.type == FT_END) {
        std::string pl = f.payload.std_str();
        auto comma = pl.find(',');
        total = atol(pl.substr(0, comma).c_str());
        bodyCrc = (uint16_t)strtoul(pl.substr(comma + 1).c_str(), nullptr, 16);
      }
    };
    for (char c : io.takeOut()) p.feed((uint8_t)c);
    CHECK(rebuilt == body, "chunked body reassembles exactly");
    CHECK(total == 1000, "END frame carries correct length");
    CHECK(crc16(String(rebuilt)) == bodyCrc, "END frame body CRC verifies");
  }

  // Frames stay under 512 bytes on the wire
  {
    std::string big(NLINK_CHUNK_PAYLOAD, 'x');
    String wire = encodeFrame(FT_DATA, 0, String(big));
    CHECK(wire.length() < 512, "max frame is <512B on the wire (" +
                                   std::to_string(wire.length()) + "B)");
  }

  std::cout << (failures ? "\nFAILURES: " : "\nAll tests passed. failures=")
            << failures << "\n";
  return failures ? 1 : 0;
}
