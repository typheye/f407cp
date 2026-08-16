/**
 ******************************************************************************
 * @file    key_activity.cpp
 * @author  Typheye
 * @brief   Key Activity implementation.
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

#include "include/key_activity.hpp"
#include "library/include/libdly.h"
#include "library/include/libui.h"

extern KeyManager keyManager;
extern LCD boardLCD;

#define KEY_N 5
#define KEY_VIS 5

void key_test_activity(void) {
  const char *key_labels[KEY_N] = {
      "00 Return", "01 KEY1 PA0", "02 KEY2 PE4", "03 KEY3 PE3",
      "04 KEY4 PE2",
  };

  int sel = 0;
  uint8_t le = 0;
  uint32_t lu = 0;

  while (1) {
    keyManager.tick();

    if (keyManager._collisionA8.getState() == KEY_PRESSED) {
      sel = (sel + 1) % KEY_N;
      JPDelay(2);
    }
    if (keyManager._collisionD0.getState() == KEY_PRESSED) {
      sel = (sel - 1 + KEY_N) % KEY_N;
      JPDelay(2);
    }

    uint8_t ce = (keyManager._btnEnter.getState() == KEY_PRESSED);
    if (ce && !le)
      return;
    le = ce;

    if (HAL_GetTick() - lu > 80U) {
      lu = HAL_GetTick();

      char key_vals[KEY_N][8];
      key_vals[0][0] = '\0';

      snprintf(key_vals[1], 8, "%s", keyManager.spare.isPressed() ? "ON" : "OFF");
      snprintf(key_vals[2], 8, "%s", keyManager.up.isPressed() ? "ON" : "OFF");
      snprintf(key_vals[3], 8, "%s", keyManager.down.isPressed() ? "ON" : "OFF");
      snprintf(key_vals[4], 8, "%s", keyManager.confirm.isPressed() ? "ON" : "OFF");

      LCD_FLUSH({
        UI_DrawFrameTitle("DEMO");
        PD_SetFont(FONT_ASCII_16);

        int vis = KEY_VIS;
        int start = sel - vis / 2;
        if (start < 0)
          start = 0;
        if (start + vis > KEY_N)
          start = KEY_N - vis;

        for (int i = 0; i < vis; i++) {
          int idx = start + i;
          if (idx >= KEY_N)
            break;
          int cy = 33 + i * 25;
          if (idx == 0)
            UI_DrawMenuCard(idx, sel, cy, key_labels[idx]);
          else
            UI_DrawMenuValue(idx, sel, cy, key_labels[idx], key_vals[idx],
                             false);
        }

        PD_DrawFooterCenter("ENTER", NULL, "UP/DOWN");
      });
    }
    JPDelay(1);
  }
}
