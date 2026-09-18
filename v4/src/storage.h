// microSD storage — everything saved in computer-legible formats:
//   /PHOTOS/IMG_0042.JPG        plain JPEGs straight from the camera
//   /CHAT/2026-08-11_001.TXT    plain-text chat transcripts
//   /FILES/...                  files pushed from the calculator
// Card is FAT32; pop it into any computer and read it.
#pragma once

#include <Arduino.h>

namespace nlink {

class Storage {
 public:
  bool begin();                          // mount card; false if absent
  bool available() const { return ok_; }

  // Photos: saves raw JPEG bytes, returns filename ("" on failure).
  String savePhoto(const uint8_t* jpeg, size_t len);

  // Chat log: appends one turn to the current session transcript.
  void logChat(const String& role, const String& text);
  void newChatSession();                 // start a fresh transcript file

  // Generic files from the calculator.
  bool saveFile(const String& name, const String& contents);
  String readFile(const String& name);   // "" if missing
  String listDir(const String& dir);     // "name<TAB>size" per line

  uint64_t freeBytes() const;

 private:
  bool ok_ = false;
  String chatFile_;
  int nextIndex(const char* dir, const char* prefix, const char* ext);
  String sanitize(const String& name);
};

}  // namespace nlink
