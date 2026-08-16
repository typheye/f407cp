/**
 ******************************************************************************
 * @file    time_activity.cpp
 * @author  Typheye
 * @brief   Time Activity implementation.
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

#include "include/time_activity.hpp"
#include "library/include/libdly.h"
#include "library/include/libui.h"

extern KeyManager keyManager;
extern LCD boardLCD;
extern TRTC boardTRTC;

static bool style_24h = true;
static char date_buf[16] = "2026-01-01";
static char time_buf[16] = "00:00:00";
static bool editing = false;
static int edit_sel = -1;

/* ==================================================================
 *  Draw
 * ================================================================== */

/* ==================================================================
 *  Main
 * ================================================================== */

void time_activity_run(void) {

  style_24h = SM_Time_Style24h();
  editing = false;
  edit_sel = -1;

  Time_t t;
  Date_t d;
  boardTRTC.getDateTime(&t, &d);
  snprintf(date_buf, sizeof(date_buf), "%04d-%02d-%02d", 2000 + d.year, d.month,
           d.date);
  /* Time item always 24H */
  snprintf(time_buf, sizeof(time_buf), "%02d:%02d:%02d", t.hours, t.minutes,
           t.seconds);

  int sel = 0;
  uint32_t lu = 0;
  bool dirty = true;

  while (1) {
    keyManager._collisionA8.tick();
    keyManager._collisionD0.tick();
    keyManager._btnEnter.tick();

    if (editing) {
      if (keyManager._collisionA8.getState() == KEY_PRESSED ||
          keyManager._collisionD0.getState() == KEY_PRESSED) {
        if (edit_sel == 3) {
          style_24h = !style_24h;
          SM_Time_SetStyle24h(style_24h);
        }
        dirty = true;
        JPDelay(2);
      }
    } else {
      if (keyManager._collisionA8.getState() == KEY_PRESSED) {
        sel = (sel + 1) % 4;
        dirty = true;
        JPDelay(2);
      }
      if (keyManager._collisionD0.getState() == KEY_PRESSED) {
        sel = (sel - 1 + 4) % 4;
        dirty = true;
        JPDelay(2);
      }
    }

    if (keyManager._btnEnter.getState() == KEY_PRESSED) {
      if (editing) {
        editing = false;
        edit_sel = -1;
      } else {
        switch (sel) {
        case 0:
          return;
        case 1:
          if (keyboard_open("Date yyyy-mm-dd", date_buf, 10)) {
            int y, mo, da;
            if (sscanf(date_buf, "%d-%d-%d", &y, &mo, &da) == 3) {
              int wk = (da + (mo <= 2 ? 1 : 0)) % 7;
              if (!wk)
                wk = 7;
              boardTRTC.setDate((uint8_t)(y - 2000), (uint8_t)mo,
                                (uint8_t)da, (uint8_t)wk);
            }
          }
          break;
        case 2:
          if (keyboard_open("Time hh:mm:ss", time_buf, 8)) {
            int h, m, s;
            if (sscanf(time_buf, "%d:%d:%d", &h, &m, &s) == 3) {
              boardTRTC.setTime((uint8_t)h, (uint8_t)m, (uint8_t)s);
            }
          }
          break;
        case 3:
          editing = true;
          edit_sel = 3;
          dirty = true;
          break;
        }
      }
    }
    if (dirty || HAL_GetTick() - lu > 80U) {
      lu = HAL_GetTick();
      dirty = false;
      boardTRTC.getDateTime(&t, &d);
      snprintf(date_buf, sizeof(date_buf), "%04d-%02d-%02d", 2000 + d.year,
               d.month, d.date);
      snprintf(time_buf, sizeof(time_buf), "%02d:%02d:%02d", t.hours,
               t.minutes, t.seconds);

      LCD_FLUSH({
        UI_DrawFrameTitle("TIME");
        PD_SetFont(FONT_ASCII_16);
        UI_DrawMenuCardEx(0, sel, 33, "00 Return", false);
        UI_DrawMenuValueEx(1, sel, 58, "01 Date", date_buf, false, false);
        UI_DrawMenuValueEx(2, sel, 83, "02 Time", time_buf, false, false);
        UI_DrawMenuValueEx(3, sel, 108, "03 Style", style_24h ? "24H" : "12H",
                           editing && edit_sel == 3, false);
        PD_DrawFooterCenter("ENTER", NULL, "UP/DOWN");
      });
    }
    JPDelay(2);
  }
}
