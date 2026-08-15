#include "include/secondary_clock.hpp"

#include "include/ssd1315.hpp"
#include "core/sys/include/syslog.h"
#include "library/include/liboledgfx.h"
#include "rtc.h"

namespace {
uint8_t frameBuffer[LIBOLEDGFX_BUFFER_SIZE];
uint8_t lastSecond = 0xFFU;
uint32_t lastFrameMs = 0U;
uint8_t wavePhase = 0U;
bool running;

const char *weekdayName(uint8_t weekday) {
  static const char *const names[] = {"---", "MON", "TUE", "WED",
                                      "THU", "FRI", "SAT", "SUN"};
  return names[weekday <= 7U ? weekday : 0U];
}

bool render(uint8_t phase) {
  RTC_TimeTypeDef time{};
  RTC_DateTypeDef date{};
  if (HAL_RTC_GetTime(&hrtc, &time, RTC_FORMAT_BIN) != HAL_OK ||
      HAL_RTC_GetDate(&hrtc, &date, RTC_FORMAT_BIN) != HAL_OK)
    return false;
  LibOledGfx_DrawDigitalClockWave(
      frameBuffer, static_cast<uint16_t>(2000U + date.Year), date.Month,
      date.Date, weekdayName(date.WeekDay), time.Hours, time.Minutes,
      time.Seconds, phase);
  if (!oled.display(frameBuffer, sizeof(frameBuffer)))
    return false;
  lastSecond = time.Seconds;
  lastFrameMs = HAL_GetTick();
  return true;
}
} // namespace

void SecondaryClock_Init() {
  running = false;
  lastSecond = 0xFFU;
  lastFrameMs = 0U;
  wavePhase = 0U;
  if (!oled.init()) {
    LOG_W("OLED", "SSD1315 not found at 0x3C/0x3D");
    return;
  }

  LibOledGfx_Clear(frameBuffer, 0U);
  if (!oled.display(frameBuffer, sizeof(frameBuffer)) || !render(wavePhase) ||
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
  uint32_t now = HAL_GetTick();
  if ((uint32_t)(now - lastFrameMs) < 250U)
    return;

  wavePhase = static_cast<uint8_t>((wavePhase + 1U) & 0x0FU);
  (void)render(wavePhase);
}
