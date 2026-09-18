#include "camera_module.h"
#include "nlink_config.h"
#include "nlink_proto.h"  // b64encode

#if NLINK_HAS_CAMERA

#include "esp_camera.h"
#include "ESP32_OV5640_AF.h"

namespace nlink {

static OV5640 ov5640;

bool Camera::begin() {
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = CAM_PIN_Y2;  c.pin_d1 = CAM_PIN_Y3;
  c.pin_d2 = CAM_PIN_Y4;  c.pin_d3 = CAM_PIN_Y5;
  c.pin_d4 = CAM_PIN_Y6;  c.pin_d5 = CAM_PIN_Y7;
  c.pin_d6 = CAM_PIN_Y8;  c.pin_d7 = CAM_PIN_Y9;
  c.pin_xclk = CAM_PIN_XCLK;
  c.pin_pclk = CAM_PIN_PCLK;
  c.pin_vsync = CAM_PIN_VSYNC;
  c.pin_href = CAM_PIN_HREF;
  c.pin_sccb_sda = CAM_PIN_SIOD;
  c.pin_sccb_scl = CAM_PIN_SIOC;
  c.pin_pwdn = CAM_PIN_PWDN;
  c.pin_reset = CAM_PIN_RESET;
  c.xclk_freq_hz = 20000000;
  c.frame_size = FRAMESIZE_VGA;
  c.pixel_format = PIXFORMAT_JPEG;
  c.grab_mode = CAMERA_GRAB_LATEST;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.jpeg_quality = 8;
  c.fb_count = 2;

  if (esp_camera_init(&c) != ESP_OK) return false;

  sensor_t* s = esp_camera_sensor_get();
  if (s && s->id.PID == OV5640_PID) {
    s->set_brightness(s, 1);
    s->set_contrast(s, 1);
    s->set_sharpness(s, 2);
    s->set_whitebal(s, 1);
    s->set_awb_gain(s, 1);
    s->set_exposure_ctrl(s, 1);
    s->set_aec2(s, 1);
    s->set_gain_ctrl(s, 1);
    s->set_hmirror(s, 1);
    ov5640.start(s);
    afOk_ = (ov5640.focusInit() == 0);
  }

  ok_ = true;
  return true;
}

void Camera::flushBuffers() {
  camera_fb_t* fb = esp_camera_fb_get();
  if (fb) esp_camera_fb_return(fb);
}

bool Camera::autofocus() {
  if (!afOk_) return false;
  sensor_t* s = esp_camera_sensor_get();
  s->set_reg(s, 0x3022, 0xFF, 0x08);
  delay(10);
  s->set_reg(s, 0x3022, 0xFF, 0x03);
  s->set_reg(s, 0x3023, 0xFF, 0x01);

  unsigned long start = millis();
  while (millis() - start < 3000) {
    if (ov5640.getFWStatus() == FW_STATUS_S_FOCUSED) return true;
    delay(50);
  }
  return false;
}

bool Camera::capture(Jpeg& out) {
  if (!ok_) return false;
  flushBuffers();
  autofocus();
  delay(200);
  flushBuffers();

  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) return false;
  out.data = fb->buf;
  out.len = fb->len;
  out.fb = fb;
  return true;
}

void Camera::release(Jpeg& jpeg) {
  if (jpeg.fb) esp_camera_fb_return((camera_fb_t*)jpeg.fb);
  jpeg = Jpeg{};
}

}  // namespace nlink

#else  // !NLINK_HAS_CAMERA — stubs for C3 builds

namespace nlink {
bool Camera::begin() { return false; }
bool Camera::autofocus() { return false; }
bool Camera::capture(Jpeg&) { return false; }
void Camera::release(Jpeg&) {}
void Camera::flushBuffers() {}
}  // namespace nlink

#endif
