// Host-side shim: just enough Arduino to compile and test nlink_proto on a PC.
#pragma once
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <algorithm>

class String {
 public:
  String() {}
  String(const char* s) : s_(s) {}
  String(const std::string& s) : s_(s) {}
  String(char c) : s_(1, c) {}
  String(int v) : s_(std::to_string(v)) {}
  String(unsigned int v) : s_(std::to_string(v)) {}
  String(long v) : s_(std::to_string(v)) {}
  String(unsigned long v) : s_(std::to_string(v)) {}
  String(size_t v, int base) {
    char buf[32];
    snprintf(buf, sizeof(buf), base == 16 ? "%zx" : "%zu", v);
    s_ = buf;
  }
  String(uint16_t v, int base) {
    char buf[32];
    snprintf(buf, sizeof(buf), base == 16 ? "%x" : "%u", (unsigned)v);
    s_ = buf;
  }

  size_t length() const { return s_.size(); }
  const char* c_str() const { return s_.c_str(); }
  void reserve(size_t n) { s_.reserve(n); }
  char operator[](size_t i) const { return s_[i]; }

  String& operator+=(char c) { s_ += c; return *this; }
  String& operator+=(const String& o) { s_ += o.s_; return *this; }
  String& operator+=(const char* o) { s_ += o; return *this; }
  friend String operator+(const String& a, const String& b) { return String(a.s_ + b.s_); }
  friend String operator+(const char* a, const String& b) { return String(a + b.s_); }
  friend String operator+(const String& a, const char* b) { return String(a.s_ + b); }
  bool operator==(const char* o) const { return s_ == o; }
  bool operator==(const String& o) const { return s_ == o.s_; }

  int indexOf(char c) const { auto p = s_.find(c); return p == std::string::npos ? -1 : (int)p; }
  int indexOf(const char* sub) const { auto p = s_.find(sub); return p == std::string::npos ? -1 : (int)p; }
  int lastIndexOf(char c) const { auto p = s_.rfind(c); return p == std::string::npos ? -1 : (int)p; }
  String substring(size_t from) const { return String(s_.substr(std::min(from, s_.size()))); }
  String substring(size_t from, size_t to) const {
    from = std::min(from, s_.size()); to = std::min(to, s_.size());
    return String(s_.substr(from, to > from ? to - from : 0));
  }
  bool startsWith(const char* p) const { return s_.rfind(p, 0) == 0; }
  void trim() {
    size_t a = s_.find_first_not_of(" \t\r\n");
    size_t b = s_.find_last_not_of(" \t\r\n");
    s_ = (a == std::string::npos) ? "" : s_.substr(a, b - a + 1);
  }

  std::string std_str() const { return s_; }

 private:
  std::string s_;
};

class Stream {
 public:
  virtual void print(const String& s) { out_ += s.std_str(); }
  virtual void flush() {}
  virtual int available() { return in_.empty() ? 0 : 1; }
  virtual int read() {
    if (in_.empty()) return -1;
    int c = (unsigned char)in_.front();
    in_.erase(in_.begin());
    return c;
  }
  void inject(const std::string& s) { in_ += s; }
  std::string takeOut() { std::string o = out_; out_.clear(); return o; }
 private:
  std::string in_, out_;
};

inline void delay(unsigned long) {}
template <typename T> T min(T a, T b) { return a < b ? a : b; }
