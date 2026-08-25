#include "storage.h"
#include "nlink_config.h"

#if NLINK_HAS_SD

#include <SD.h>
#include <SPI.h>
#include <time.h>

namespace nlink {

static const char* DIR_PHOTOS = "/PHOTOS";
static const char* DIR_CHAT = "/CHAT";
static const char* DIR_FILES = "/FILES";

// Date prefix like "2026-08-11" if NTP time is available, else "".
static String datePrefix() {
  time_t now = time(nullptr);
  if (now < 1600000000) return "";  // clock not set
  struct tm t;
  localtime_r(&now, &t);
  char buf[16];
  strftime(buf, sizeof(buf), "%Y-%m-%d", &t);
  return String(buf);
}

bool Storage::begin() {
#ifdef NLINK_SD_CS
  ok_ = SD.begin(NLINK_SD_CS);
#else
  ok_ = SD.begin();
#endif
  if (!ok_) return false;
  SD.mkdir(DIR_PHOTOS);
  SD.mkdir(DIR_CHAT);
  SD.mkdir(DIR_FILES);
  newChatSession();
  return true;
}

int Storage::nextIndex(const char* dir, const char* prefix, const char* ext) {
  int maxIdx = 0;
  File d = SD.open(dir);
  if (!d) return 1;
  for (File f = d.openNextFile(); f; f = d.openNextFile()) {
    String name = f.name();
    int p = name.indexOf(prefix);
    if (p >= 0) {
      int idx = name.substring(p + strlen(prefix)).toInt();
      if (idx > maxIdx) maxIdx = idx;
    }
    f.close();
  }
  d.close();
  return maxIdx + 1;
}

String Storage::savePhoto(const uint8_t* jpeg, size_t len) {
  if (!ok_) return "";
  int idx = nextIndex(DIR_PHOTOS, "IMG_", ".JPG");
  char name[40];
  snprintf(name, sizeof(name), "%s/IMG_%04d.JPG", DIR_PHOTOS, idx);
  File f = SD.open(name, FILE_WRITE);
  if (!f) return "";
  size_t written = f.write(jpeg, len);
  f.close();
  if (written != len) { SD.remove(name); return ""; }
  return String(name);
}

void Storage::newChatSession() {
  if (!ok_) return;
  int idx = nextIndex(DIR_CHAT, "CHAT_", ".TXT");
  String date = datePrefix();
  char name[48];
  if (date.length())
    snprintf(name, sizeof(name), "%s/%s_CHAT_%03d.TXT", DIR_CHAT, date.c_str(), idx);
  else
    snprintf(name, sizeof(name), "%s/CHAT_%03d.TXT", DIR_CHAT, idx);
  chatFile_ = name;
}

void Storage::logChat(const String& role, const String& text) {
  if (!ok_ || chatFile_ == "") return;
  File f = SD.open(chatFile_.c_str(), FILE_APPEND);
  if (!f) return;
  f.print("[" + role + "]\n");
  f.print(text);
  f.print("\n\n");
  f.close();
}

String Storage::sanitize(const String& name) {
  String out;
  for (size_t i = 0; i < name.length(); i++) {
    char c = name[i];
    if (isalnum(c) || c == '.' || c == '_' || c == '-') out += c;
  }
  if (out == "" || out[0] == '.') out = "FILE_" + out;
  return out;
}

bool Storage::saveFile(const String& name, const String& contents) {
  if (!ok_) return false;
  String path = String(DIR_FILES) + "/" + sanitize(name);
  File f = SD.open(path.c_str(), FILE_WRITE);
  if (!f) return false;
  f.print(contents);
  f.close();
  return true;
}

String Storage::readFile(const String& name) {
  if (!ok_) return "";
  String path = String(DIR_FILES) + "/" + sanitize(name);
  File f = SD.open(path.c_str(), FILE_READ);
  if (!f) return "";
  String out;
  out.reserve(f.size());
  while (f.available()) out += (char)f.read();
  f.close();
  return out;
}

String Storage::listDir(const String& dir) {
  if (!ok_) return "";
  String path = dir;
  if (!path.startsWith("/")) path = "/" + path;
  File d = SD.open(path.c_str());
  if (!d || !d.isDirectory()) return "";
  String out;
  for (File f = d.openNextFile(); f; f = d.openNextFile()) {
    out += String(f.name()) + "\t" + String((unsigned long)f.size()) + "\n";
    f.close();
  }
  d.close();
  return out;
}

uint64_t Storage::freeBytes() const {
  if (!ok_) return 0;
  return SD.totalBytes() - SD.usedBytes();
}

}  // namespace nlink

#else  // !NLINK_HAS_SD — lite build: SD compiled out entirely

namespace nlink {
bool Storage::begin() { ok_ = false; return false; }
String Storage::savePhoto(const uint8_t*, size_t) { return ""; }
void Storage::newChatSession() {}
void Storage::logChat(const String&, const String&) {}
bool Storage::saveFile(const String&, const String&) { return false; }
String Storage::readFile(const String&) { return ""; }
String Storage::listDir(const String&) { return ""; }
uint64_t Storage::freeBytes() const { return 0; }
int Storage::nextIndex(const char*, const char*, const char*) { return 0; }
String Storage::sanitize(const String&) { return ""; }
}  // namespace nlink

#endif
