/**
 ******************************************************************************
 * @file    display_activity.cpp
 * @author  Typheye
 * @brief   Display Activity implementation.
 ******************************************************************************
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 *
 */

#include "include/display_activity.hpp"
#include "library/include/libdly.h"
#include "library/include/libui.h"

extern KeyManager keyManager;
extern LCD boardLCD;

static int disp_bright = 10; // 1-10
static bool disp_inited = false; // only apply defaults first time

static const char *auto_close_names[] = {"OFF", "ON"};
static const char *delay_names[] = {"15s", "30s", "1min", "2min", "5min", "10min"};

static void apply(void) {
  boardLCD.setBrightness((uint16_t)disp_bright * 100);
}

static int item_count(void) {
  return 5; // Return + Brightness + Resolution + AutoClose + Delay
}

static void draw_disp(int sel, bool editing, int edit_field, bool auto_close,
                      uint8_t sleep_delay) {
  LCD_FLUSH({
    UI_DrawFrameTitle("DISP");
    PD_SetFont(FONT_ASCII_16);

    int n = item_count();
    int vis = n < 7 ? n : 7;
    int start = UI_MenuVisibleStart(n, sel, vis);

    for (int i = 0; i < vis; i++) {
      int idx = start + i;
      if (idx >= n)
        break;
      int cy = 33 + i * 25;

      switch (idx) {
      case 0:
        UI_DrawMenuCard(idx, sel, cy, "00 Return");
        break;
      case 1: {
        char buf[32];
        snprintf(buf, sizeof(buf), "01 Brightness");
        char val[8];
        snprintf(val, sizeof(val), "%d%%", disp_bright * 10);
        UI_DrawMenuValue(idx, sel, cy, buf, val, editing && edit_field == 1);
        break;
      }
      case 2:
        UI_DrawMenuCard(idx, sel, cy, "02 Resolution  240x240");
        break;
      case 3: {
        UI_DrawMenuValueEx(idx, sel, cy, "03 Auto Close",
                           auto_close_names[auto_close ? 1 : 0],
                           editing && edit_field == 3, false);
        break;
      }
      case 4: {
        UI_DrawMenuValueEx(idx, sel, cy, "   Delay", delay_names[sleep_delay],
                           editing && edit_field == 4, !auto_close);
        break;
      }
      }
    }
    UI_DrawStdFooter();
  });
}

// ============ Main ============

void display_activity_run(void) {
  if (!disp_inited) {
    disp_bright = SM_Disp_Bright();
    disp_inited = true;
  }
  boardLCD.setBrightness((uint16_t)disp_bright * 100);
  bool auto_close = SM_Disp_AutoClose();
  uint8_t sleep_delay = SM_Disp_CloseDelay();
  bool editing = false;
  int edit_field = 0;

  int sel = 0;
  uint32_t lu = 0;
  bool dirty = true;

  while (1) {
    TosApi_Tick();
    if (keyManager._collisionA8.getState() == KEY_PRESSED) {
      if (editing) {
        if (edit_field == 1) {
          disp_bright++;
          if (disp_bright > 10)
            disp_bright = 10;
          apply(); /* live preview */
        } else if (edit_field == 3) {
          auto_close = true;
        } else if (edit_field == 4) {
          sleep_delay = (uint8_t)((sleep_delay + 1U) % 6U);
        }
      } else {
        sel = (sel + 1) % item_count();
      }
      dirty = true;
      JPDelay(2);
    }
    if (keyManager._collisionD0.getState() == KEY_PRESSED) {
      if (editing) {
        if (edit_field == 1) {
          disp_bright--;
          if (disp_bright < 1)
            disp_bright = 1;
          apply(); /* live preview */
        } else if (edit_field == 3) {
          auto_close = false;
        } else if (edit_field == 4) {
          sleep_delay = (uint8_t)((sleep_delay + 5U) % 6U);
        }
      } else {
        sel = (sel - 1 + item_count()) % item_count();
      }
      dirty = true;
      JPDelay(2);
    }

    if (keyManager._btnEnter.getState() == KEY_PRESSED) {
      if (editing) {
        editing = false;
        edit_field = 0;
        SM_Disp_SetConfig((uint8_t)disp_bright, auto_close, sleep_delay);
        boardLCD.setBrightness((uint16_t)disp_bright * 100);
        dirty = true;
      } else {
        if (sel == 0) {
          return;
        }
        if (sel == 1) {
          editing = true;
          edit_field = 1;
        }
        if (sel == 3) {
          editing = true;
          edit_field = 3;
        }
        if (sel == 4 && auto_close) {
          editing = true;
          edit_field = 4;
        }
        dirty = true;
      }
    }
    if (dirty || HAL_GetTick() - lu > 80U) {
      lu = HAL_GetTick();
      dirty = false;
      draw_disp(sel, editing, edit_field, auto_close, sleep_delay);
    }
    JPDelay(1);
  }
}
