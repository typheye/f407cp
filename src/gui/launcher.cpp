/**
 ******************************************************************************
 * @file    launcher.cpp
 * @author  Typheye
 * @brief   Home launcher implementation.
 ******************************************************************************
 */

#include "include/launcher.hpp"
#include "core/manager/include/app_manager.h"
#include "gui/demo/include/demo_activity.hpp"
#include "gui/include/settings.hpp"
#include "gui/miniapp/file_manager/include/app.h"
#include "library/include/libdly.h"
#include "library/include/libpd.h"
#include "library/include/libui.h"
#include <cstring>

extern KeyManager keyManager;

static void launcher_wait_enter_release(void) {
  while (keyManager._btnEnter.isPressed()) {
    TosApi_Tick();
    SysWatchdog_Tick();
    JPDelay(1U);
  }
  keyManager._btnEnter.tick();
  (void)keyManager._btnEnter.getState();
}

static uint16_t launcher_visible(uint16_t *indices, uint16_t cap) {
  uint16_t count = 0U;
  const uint16_t total = AppManager_Count();
  for (uint16_t i = 0U; i < total && count < cap; ++i) {
    const AppManager_App *app = AppManager_Get(i);
    if (app && !app->hidden) indices[count++] = i;
  }
  return count;
}

static const char *launcher_fit_name(const char *name) {
  static char out[24];
  strncpy(out, name ? name : "", sizeof(out) - 1U);
  out[sizeof(out) - 1U] = '\0';
  if (PD_GetStringWidth(out) <= 68U) return out;
  size_t len = strlen(out);
  while (len > 3U) {
    out[len - 3U] = '.';
    out[len - 2U] = '.';
    out[len - 1U] = '.';
    out[len] = '\0';
    if (PD_GetStringWidth(out) <= 68U) return out;
    --len;
  }
  return "...";
}

static void launcher_draw(int sel, const uint16_t *visible,
                          uint16_t visible_count) {
  const int page = sel / 6;
  const int pages = visible_count > 0U ? ((int)visible_count + 5) / 6 : 1;
  LCD_FLUSH({
    UI_DrawFrameTitle("HOME");
    const int16_t x0 = 12;
    const int16_t y0 = 36;
    const int16_t cell_w = 68;

    for (int slot = 0; slot < 6; ++slot) {
      const int item = page * 6 + slot;
      if (item >= (int)visible_count) continue;
      const AppManager_App *app = AppManager_Get(visible[item]);
      if (!app) continue;

      const int16_t x = x0 + (slot % 3) * 75;
      const int16_t y = y0 + (slot / 3) * 76;
      const bool selected = item == sel;
      PD_SetFont(FONT_ASCII_12);
      const char *name = launcher_fit_name(app->name);

      PD_FillRect(x + 16, y + 3, 36, 36,
                  selected ? TOS_TEXT : TOS_ACCENT);
      if (selected) {
        PD_SetColor(TOS_ACCENT);
        PD_SetFill(false);
        PD_DrawRect(x + 13, y, 42, 42);
      }

      char initial[2] = {name[0], '\0'};
      PD_SetColor(selected ? TOS_ACCENT : TOS_BG);
      PD_SetFont(FONT_ASCII_24);
      PD_DrawStringCentered(x + 16, y + 3, 36, 36, initial);
      PD_SetColor(selected ? TOS_TEXT : TOS_TEXT_SEC);
      PD_SetFont(FONT_ASCII_12);
      PD_DrawStringCentered(x, y + 45, cell_w, 16, name);
    }

    const int16_t track_x = 90;
    const int16_t track_y = 190;
    const int16_t track_w = 60;
    const int16_t gap = 3;
    const int16_t thumb_w = (track_w - (pages - 1) * gap) / pages;
    PD_FillRect(track_x, track_y, track_w, 4, TOS_CARD_BG);
    PD_FillRect(track_x + page * (thumb_w + gap), track_y, thumb_w, 4,
                TOS_ACCENT);
    PD_DrawFooterCenter("ENTER", NULL, "UP/DOWN");
  });
}

static void launcher_run_app(const AppManager_App *app) {
  if (strcmp(app->package_name, "tos.file") == 0)
    file_manager_run();
  else if (strcmp(app->package_name, "tos.settings") == 0)
    settings_run();
  else if (strcmp(app->package_name, "tos.demo") == 0)
    demo_list_run();
}

void petLauncherRun(void) {
  static int sel = 0;
  uint16_t visible[APP_MANAGER_MAX];
  (void)AppManager_Init();
  uint32_t last_draw = HAL_GetTick() - 81U;

  while (1) {
    uint16_t count = launcher_visible(visible, APP_MANAGER_MAX);
    if (count == 0U)
      sel = 0;
    else if (sel >= (int)count)
      sel = (int)count - 1;

    TosApi_Tick();
    SysWatchdog_Tick();
    keyManager._collisionA8.tick();
    keyManager._collisionD0.tick();
    keyManager._btnEnter.tick();

    if (count > 0U && keyManager._collisionA8.getState() == KEY_PRESSED) {
      sel = (sel + 1) % (int)count;
      last_draw = HAL_GetTick() - 81U;
      JPDelay(2U);
    }
    if (count > 0U && keyManager._collisionD0.getState() == KEY_PRESSED) {
      sel = (sel + (int)count - 1) % (int)count;
      last_draw = HAL_GetTick() - 81U;
      JPDelay(2U);
    }

    if (count > 0U && keyManager._btnEnter.getState() == KEY_PRESSED) {
      const AppManager_App *app = AppManager_Get(visible[sel]);
      if (app) launcher_run_app(app);
      launcher_wait_enter_release();
      last_draw = HAL_GetTick() - 81U;
    }

    if ((uint32_t)(HAL_GetTick() - last_draw) > 80U) {
      last_draw = HAL_GetTick();
      launcher_draw(sel, visible, count);
    }
    JPDelay(1U);
  }
}
