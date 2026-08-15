#include "include/sysui.hpp"

#include "core/sys/include/syswatchdog.h"
#include "fatfs.h"
#include "hardware/include/key.hpp"
#include "hardware/include/lcd.hpp"
#include "hardware/include/cdc_bridge.h"
#include "hardware/include/secondary_clock.hpp"
#include "library/include/libdly.h"
#include "library/include/libpd.h"
#include "library/include/libui.h"
#include "rtc.h"

#include <cstdio>

namespace {
constexpr int kMenuCount = 6;
const char *kMenuItems[kMenuCount] = {
    "00 Status", "01 SD Card", "02 Network", "03 RTC Clock",
    "04 Display", "05 System",
};
int selected;
uint32_t lastDraw;

void backgroundTick() {
  CDC_Bridge_Tick();
  SecondaryClock_Tick();
  SysWatchdog_Tick();
}

void drawLines(const char *title, const char *line1, const char *line2,
               const char *line3, const char *line4 = nullptr) {
  LCD_FLUSH({
    UI_DrawFrameTitle(title);
    PD_SetFont(FONT_ASCII_16);
    PD_SetColor(TOS_TEXT);
    if (line1)
      PD_DrawString(22, 44, line1);
    if (line2)
      PD_DrawString(22, 74, line2);
    if (line3)
      PD_DrawString(22, 104, line3);
    if (line4)
      PD_DrawString(22, 134, line4);
    PD_DrawFooterCenter(nullptr, "BACK", nullptr);
  });
}

void waitBack() {
  while (true) {
    keyManager.tick();
    if (keyManager.spare.getState() == KEY_PRESSED ||
        keyManager.confirm.getState() == KEY_PRESSED)
      return;
    backgroundTick();
    JPDelay(2U);
  }
}

void showStatus() {
  RTC_TimeTypeDef time{};
  RTC_DateTypeDef date{};
  (void)HAL_RTC_GetTime(&hrtc, &time, RTC_FORMAT_BIN);
  (void)HAL_RTC_GetDate(&hrtc, &date, RTC_FORMAT_BIN);
  char clock[32];
  char brightness[32];
  snprintf(clock, sizeof(clock), "%04u-%02u-%02u  %02u:%02u:%02u",
           2000U + date.Year, date.Month, date.Date, time.Hours, time.Minutes,
           time.Seconds);
  snprintf(brightness, sizeof(brightness), "Backlight: %u%%",
           boardLCD.getBrightness() / 10U);
  drawLines("STATUS", clock, "USB CDC: READY", brightness,
            SysWatchdog_GetBootText());
  waitBack();
}

void showSd() {
  FRESULT result = f_mount(&SDFatFS, SDPath, 1U);
  char state[36];
  char totalText[36] = "Capacity: unavailable";
  char freeText[36] = "Free: unavailable";
  if (result == FR_OK) {
    DWORD freeClusters = 0U;
    FATFS *fs = nullptr;
    result = f_getfree(SDPath, &freeClusters, &fs);
    if (result == FR_OK && fs != nullptr) {
      const uint64_t totalKb =
          ((uint64_t)(fs->n_fatent - 2U) * fs->csize) / 2U;
      const uint64_t freeKb = ((uint64_t)freeClusters * fs->csize) / 2U;
      snprintf(totalText, sizeof(totalText), "Capacity: %lu MB",
               (unsigned long)(totalKb / 1024U));
      snprintf(freeText, sizeof(freeText), "Free: %lu MB",
               (unsigned long)(freeKb / 1024U));
    }
  }
  snprintf(state, sizeof(state), "SD status: %s (%d)",
           result == FR_OK ? "mounted" : "not ready", (int)result);
  drawLines("SD CARD", state, totalText, freeText, "Read-only status page");
  waitBack();
}

void showNetwork() {
  drawLines("NETWORK", "Transport: USB CDC", "ESP8266: not installed",
            "Network stack: offline", "UART1 bridge: enabled");
  waitBack();
}

void showClock() {
  while (true) {
    RTC_TimeTypeDef time{};
    RTC_DateTypeDef date{};
    (void)HAL_RTC_GetTime(&hrtc, &time, RTC_FORMAT_BIN);
    (void)HAL_RTC_GetDate(&hrtc, &date, RTC_FORMAT_BIN);
    char dateText[32];
    char timeText[32];
    char weekday[24];
    static const char *const names[] = {"?", "MONDAY", "TUESDAY", "WEDNESDAY",
                                        "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"};
    snprintf(dateText, sizeof(dateText), "Date: %04u-%02u-%02u",
             2000U + date.Year, date.Month, date.Date);
    snprintf(timeText, sizeof(timeText), "Time: %02u:%02u:%02u", time.Hours,
             time.Minutes, time.Seconds);
    snprintf(weekday, sizeof(weekday), "Weekday: %s",
             names[date.WeekDay <= 7U ? date.WeekDay : 0U]);
    drawLines("RTC CLOCK", dateText, weekday, timeText, "Source: LSE / RTC");
    keyManager.tick();
    if (keyManager.spare.getState() == KEY_PRESSED ||
        keyManager.confirm.getState() == KEY_PRESSED)
      return;
    backgroundTick();
    JPDelay(50U);
  }
}

void showDisplay() {
  while (true) {
    char value[32];
    snprintf(value, sizeof(value), "Brightness: %u%%",
             boardLCD.getBrightness() / 10U);
    drawLines("DISPLAY", value, "KEY1: brighter", "KEY2: dimmer",
              "Manual mode / saved");
    keyManager.tick();
    if (keyManager.up.getState() == KEY_PRESSED)
      boardLCD.adjustBrightness(100);
    if (keyManager.down.getState() == KEY_PRESSED)
      boardLCD.adjustBrightness(-100);
    if (keyManager.spare.getState() == KEY_PRESSED ||
        keyManager.confirm.getState() == KEY_PRESSED)
      return;
    backgroundTick();
    JPDelay(25U);
  }
}

void showSystem() {
  char code[32];
  snprintf(code, sizeof(code), "Reset code: %lu",
           (unsigned long)SysWatchdog_GetBootCode());
  drawLines("SYSTEM", "Fault LED: disabled", "Text alerts: enabled", code,
            SysWatchdog_GetBootText());
  waitBack();
}

void openSelected() {
  switch (selected) {
  case 0: showStatus(); break;
  case 1: showSd(); break;
  case 2: showNetwork(); break;
  case 3: showClock(); break;
  case 4: showDisplay(); break;
  default: showSystem(); break;
  }
  lastDraw = 0U;
}
} // namespace

void SysUI::init() {
  selected = 0;
  lastDraw = 0U;
  PD_Init();
}

void SysUI::loop() {
  backgroundTick();
  keyManager.tick();
  if (keyManager.up.getState() == KEY_PRESSED) {
    selected = (selected - 1 + kMenuCount) % kMenuCount;
    lastDraw = 0U;
  }
  if (keyManager.down.getState() == KEY_PRESSED) {
    selected = (selected + 1) % kMenuCount;
    lastDraw = 0U;
  }
  if (keyManager.confirm.getState() == KEY_PRESSED)
    openSelected();

  if ((uint32_t)(HAL_GetTick() - lastDraw) >= 100U) {
    lastDraw = HAL_GetTick();
    UI_DrawSimpleMenu("TOS", kMenuItems, kMenuCount, selected);
  }
}
