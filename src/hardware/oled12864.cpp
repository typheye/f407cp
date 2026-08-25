#include "include/oled12864.hpp"

#include "include/ssd1315.hpp"
#include "core/manager/include/settings_manager.h"
#include "core/sys/include/syslog.h"
#include "library/include/liboledgfx.h"
#include "rtc.h"

namespace {
uint8_t frameBuffer[LIBOLEDGFX_BUFFER_SIZE];
uint32_t lastFrameMs = 0U;
uint32_t lastSeenSeq = 0U;
uint32_t lastForceRefreshMs = 0U;
uint8_t wavePhase = 0U;
uint8_t pendingPage = 8U;
uint8_t pageRetry = 0U;
uint8_t mode = SM_OLED_CLOCK;
bool running = false;
bool powerEnabled = true;
bool panelOn = false;

const char *weekdayName(uint8_t weekday) {
  static const char *const names[] = {"---", "MON", "TUE", "WED",
                                      "THU", "FRI", "SAT", "SUN"};
  return names[weekday <= 7U ? weekday : 0U];
}

bool drawClockScreen() {
  RTC_TimeTypeDef time{};
  RTC_DateTypeDef date{};
  if (HAL_RTC_GetTime(&hrtc, &time, RTC_FORMAT_BIN) != HAL_OK ||
      HAL_RTC_GetDate(&hrtc, &date, RTC_FORMAT_BIN) != HAL_OK)
    return false;
  LibOledGfx_DrawDigitalClockWave(
      frameBuffer, static_cast<uint16_t>(2000U + date.Year), date.Month,
      date.Date, weekdayName(date.WeekDay), time.Hours, time.Minutes,
      time.Seconds, wavePhase);
  return true;
}

void drawLogScreen() {
  char lines[9][32];
  const uint32_t count = SysLog_OledSnapshot(lines, 9U);
  LibOledGfx_Clear(frameBuffer, 0U);
  for (uint32_t i = 0U; i < count; ++i)
    LibOledGfx_DrawText3x5(frameBuffer, 0U, static_cast<uint8_t>(i * 7U),
                           lines[i]);
}

void composeCurrentMode() {
  if (mode == SM_OLED_CLOCK) {
    (void)drawClockScreen();
  } else if (mode == SM_OLED_LOG) {
    lastSeenSeq = SysLog_OledSequence();
    drawLogScreen();
  } else {
    LibOledGfx_Clear(frameBuffer, 0U);
  }
}

void startPagedRefresh() {
  pendingPage = 0U;
  pageRetry = 0U;
}

void servicePagedRefresh() {
  if (pendingPage >= 8U || oled.busy())
    return;
  if (oled.displayPage(pendingPage, &frameBuffer[pendingPage * 128U])) {
    pendingPage++;
    pageRetry = 0U;
  } else if (++pageRetry > 8U) {
    pendingPage = 8U;
    pageRetry = 0U;
  }
}

void setPanelOn(bool enabled) {
  if (panelOn == enabled)
    return;
  if (oled.setDisplayOn(enabled))
    panelOn = enabled;
}
} // namespace

void Oled12864_Init() {
  running = false;
  powerEnabled = true;
  panelOn = false;
  mode = SM_OledMode();
  lastFrameMs = 0U;
  lastSeenSeq = 0U;
  lastForceRefreshMs = 0U;
  wavePhase = 0U;
  pendingPage = 8U;
  pageRetry = 0U;

  if (!oled.init()) {
    LOG_W("OLED", "SSD1315 not found at 0x3C/0x3D");
    return;
  }

  LibOledGfx_Clear(frameBuffer, 0U);
  (void)oled.display(frameBuffer, sizeof(frameBuffer));
  running = true;
  if (mode == SM_OLED_OFF) {
    (void)oled.setDisplayOn(false);
    LOG_I("OLED", "SSD1315 ready at 0x%02X, mode=OFF", oled.address());
    return;
  }

  composeCurrentMode();
  (void)oled.display(frameBuffer, sizeof(frameBuffer));
  setPanelOn(true);
  startPagedRefresh();
  LOG_I("OLED", "SSD1315 ready at 0x%02X, mode=%s", oled.address(),
        mode == SM_OLED_CLOCK ? "CLOCK" : "LOG");
}

void Oled12864_Tick() {
  if (!running || !powerEnabled || mode == SM_OLED_OFF || !panelOn)
    return;
  servicePagedRefresh();
  if (pendingPage < 8U)
    return;

  const uint32_t now = HAL_GetTick();
  if (mode == SM_OLED_CLOCK) {
    if ((uint32_t)(now - lastFrameMs) < 250U)
      return;
    lastFrameMs = now;
    wavePhase = static_cast<uint8_t>((wavePhase + 1U) & 0x0FU);
    if (drawClockScreen())
      startPagedRefresh();
    return;
  }

  if ((uint32_t)(now - lastFrameMs) < 150U)
    return;
  lastFrameMs = now;
  const uint32_t seq = SysLog_OledSequence();
  const bool changed = seq != lastSeenSeq;
  const bool force = (uint32_t)(now - lastForceRefreshMs) >= 1000U;
  if (!changed && !force)
    return;
  lastSeenSeq = seq;
  lastForceRefreshMs = now;
  drawLogScreen();
  startPagedRefresh();
}

void Oled12864_SetDisplayOn(bool enabled) {
  powerEnabled = enabled;
  if (!running)
    return;
  if (!enabled || mode == SM_OLED_OFF) {
    pendingPage = 8U;
    setPanelOn(false);
    return;
  }
  composeCurrentMode();
  setPanelOn(true);
  lastFrameMs = 0U;
  lastForceRefreshMs = 0U;
  startPagedRefresh();
}

void Oled12864_SetMode(uint8_t nextMode) {
  if (nextMode > SM_OLED_LOG)
    nextMode = SM_OLED_CLOCK;
  mode = nextMode;
  pendingPage = 8U;
  pageRetry = 0U;
  if (!running)
    return;
  if (mode == SM_OLED_OFF || !powerEnabled) {
    setPanelOn(false);
    return;
  }
  composeCurrentMode();
  setPanelOn(true);
  lastFrameMs = 0U;
  lastForceRefreshMs = 0U;
  startPagedRefresh();
}
