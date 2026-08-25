// OV5640 camera on ESP32-S3 (DVP) with autofocus. Compiled out on C3 builds.
#pragma once

#include <Arduino.h>

namespace nlink {

// A captured JPEG. Borrowing the driver's frame buffer — call
// Camera::release() when done (before the next capture).
struct Jpeg {
  const uint8_t* data = nullptr;
  size_t len = 0;
  void* fb = nullptr;   // opaque camera_fb_t*
};

class Camera {
 public:
  bool begin();                 // init sensor; returns false if unavailable
  bool available() const { return ok_; }
  bool autofocus();             // trigger AF, wait for lock (<=3 s)
  bool capture(Jpeg& out);      // AF + capture; false on failure
  void release(Jpeg& jpeg);

 private:
  bool ok_ = false;
  bool afOk_ = false;
  void flushBuffers();
};

}  // namespace nlink
