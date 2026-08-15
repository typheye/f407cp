#include "include/secondary_clock.hpp"

#include "include/ssd1315.hpp"
#include "core/sys/include/syslog.h"
#include "library/include/liboledgfx.h"
#include "rtc.h"

namespace {
uint8_t frameBuffer[LIBOLEDGFX_BUFFER_SIZE];
uint8_t lastSecond = 0xFFU;
bool running;

const char *weekdayName(uint8_t weekday) {
  static const char *const names[] = {"---", "MON", "TUE", "WED",
                                      "THU", "FRI", "SAT", "SUN"};
  return names[weekday <= 7U ? weekday : 0U];
}

bool render() {
  RTC_TimeTypeDef time{};
  RTC_DateTypeDef date{};
  if (HAL_RTC_GetTime(&hrtc, &time, RTC_FORMAT_BIN) != HAL_OK ||
      HAL_RTC_GetDate(&hrtc, &date, RTC_FORMAT_BIN) != HAL_OK)
    return false;
  LibOledGfx_DrawDigitalClock(frameBuffer,
                              static_cast<uint16_t>(2000U + date.Year),
                              date.Month, date.Date, weekdayName(date.WeekDay),
                              time.Hours, time.Minutes, time.Seconds);
  if (!oled.display(frameBuffer, sizeof(frameBuffer)))
    return false;
  lastSecond = time.Seconds;
  return true;
}
} // namespace

void SecondaryClock_Init() {
  running = false;
  lastSecond = 0xFFU;
  if (!oled.init()) {
    LOG_W("OLED", "SSD1315 not found at 0x3C/0x3D");
    return;
  }

  LibOledGfx_Clear(frameBuffer, 0U);
  if (!oled.display(frameBuffer, sizeof(frameBuffer)) || !render() ||
      !oled.setDisplayOn(true)) {
    (void)oled.setDisplayOn(false);
    LOG_W("OLED", "SSD1315 clock initialization failed");
    return;
  }
  running = true;
  LOG_I("OLED", "SSD1315 clock ready at 0x%02X", oled.address());
}

void SecondaryClock_Tick() {
  if (!running)
    return;
  RTC_TimeTypeDef time{};
  RTC_DateTypeDef date{};
  if (HAL_RTC_GetTime(&hrtc, &time, RTC_FORMAT_BIN) == HAL_OK &&
      HAL_RTC_GetDate(&hrtc, &date, RTC_FORMAT_BIN) == HAL_OK &&
      time.Seconds != lastSecond)
    (void)render();
}
