#include "include/libui.h"

#include "hardware/include/key.hpp"
#include "hardware/include/lcd.hpp"
#include "include/libdly.h"
#include "include/libpd.h"
#include "rtc.h"

#include <cstdio>

extern KeyManager keyManager;

void UI_DrawFrameTitle(const char *title) {
  PD_Init();
  PD_FillScreen(TOS_BG);
  RTC_TimeTypeDef time{};
  RTC_DateTypeDef date{};
  (void)HAL_RTC_GetTime(&hrtc, &time, RTC_FORMAT_BIN);
  (void)HAL_RTC_GetDate(&hrtc, &date, RTC_FORMAT_BIN);
  char text[8];
  snprintf(text, sizeof(text), "%02u:%02u", time.Hours, time.Minutes);
  PD_SetHeaderTime(text);
  PD_DrawFrame();
  PD_SetFont(FONT_ASCII_16);
  PD_SetColor(TOS_ACCENT);
  PD_DrawString(22, 5, title);
}

void UI_DrawFrameStatusIcons(void) {}

void UI_DrawMenuCardEx(int idx, int sel, int cy, const char *text, bool grey) {
  const bool selected = idx == sel;
  PD_DrawAngledCard(14, cy, 212, 20, 5,
                    selected ? TOS_ACCENT : TOS_CARD_BG);
  PD_SetColor(grey ? TOS_GREY : (selected ? TOS_TEXT : TOS_TEXT_SEC));
  PD_DrawString(26, cy + 2, text);
}

void UI_DrawMenuCard(int idx, int sel, int cy, const char *text) {
  UI_DrawMenuCardEx(idx, sel, cy, text, false);
}

void UI_DrawMenuValue(int idx, int sel, int cy, const char *label,
                      const char *value, bool editing) {
  const bool selected = idx == sel;
  uint32_t color = selected ? TOS_ACCENT : TOS_CARD_BG;
  if (selected && editing && ((HAL_GetTick() / 300U) & 1U) != 0U)
    color = TOS_CARD_BG;
  PD_DrawAngledCard(14, cy, 212, 20, 5, color);
  PD_SetColor(selected ? TOS_TEXT : TOS_TEXT_SEC);
  PD_DrawString(26, cy + 2, label);
  if (value != nullptr) {
    const uint16_t width = PD_GetStringWidth(value);
    PD_DrawString(220 - width, cy + 2, value);
  }
}

void UI_DrawMenuValueEx(int idx, int sel, int cy, const char *label,
                        const char *value, bool editing, bool grey) {
  UI_DrawMenuValue(idx, sel, cy, label, value, editing);
  (void)grey;
}

void UI_DrawMenuBool(int idx, int sel, int cy, const char *label, bool on,
                     bool editing) {
  UI_DrawMenuValue(idx, sel, cy, label, on ? "ON" : "OFF", editing);
}

void UI_DrawStdFooter(void) { PD_DrawFooterCenter("ENTER", "BACK", "UP/DOWN"); }

int UI_MenuVisibleStart(int count, int sel, int visible) {
  int start = sel - visible / 2;
  if (start < 0)
    start = 0;
  if (start + visible > count)
    start = count - visible;
  return start < 0 ? 0 : start;
}

void UI_DrawSimpleMenu(const char *title, const char **items, int count,
                       int sel) {
  LCD_FLUSH({
    UI_DrawFrameTitle(title);
    PD_SetFont(FONT_ASCII_16);
    const int visible = count < 7 ? count : 7;
    const int start = UI_MenuVisibleStart(count, sel, visible);
    for (int i = 0; i < visible; ++i)
      UI_DrawMenuCard(start + i, sel, 33 + i * 25, items[start + i]);
    UI_DrawStdFooter();
  });
}

int UI_MenuLoop(const char *title, const char **items, int count,
                int startSel) {
  int selected = startSel;
  uint32_t lastDraw = 0U;
  while (true) {
    keyManager.tick();
    if (keyManager.up.getState() == KEY_PRESSED)
      selected = (selected - 1 + count) % count;
    if (keyManager.down.getState() == KEY_PRESSED)
      selected = (selected + 1) % count;
    if (keyManager.confirm.getState() == KEY_PRESSED)
      return selected;
    if (keyManager.spare.getState() == KEY_PRESSED)
      return -1;
    if ((uint32_t)(HAL_GetTick() - lastDraw) >= 40U) {
      lastDraw = HAL_GetTick();
      UI_DrawSimpleMenu(title, items, count, selected);
    }
    JPDelay(2U);
  }
}
