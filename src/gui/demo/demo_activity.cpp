/**
 ******************************************************************************
 * @file    demo_activity.cpp
 * @author  Typheye
 * @brief   Demo Activity implementation.
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

#include "include/demo_activity.hpp"
#include "hardware/include/led.hpp"
#include "library/include/libdly.h"
#include "library/include/libui.h"


extern KeyManager keyManager;
extern LCD boardLCD;
extern LED redLed;
extern LED greenLed;
extern LED blueLed;
extern LED whiteLed;

static void led_test_activity(void);

#define DEMO_ITEMS 5
static const char *demo_m[DEMO_ITEMS] = {
    "00 Return", "01 Key Test", "02 LED Test", "03 I2C Scan",
    "04 3D Path Tracer",
};
static void (*demo_f[DEMO_ITEMS])(void) = {
    NULL,
    key_test_activity,
    led_test_activity,
    i2c_scan_activity,
    render_3dox_activity_with_exit,
};

// ============ Original TOS-style menu ============

void demo_list_run(void) {
  static int sel = 0;
  while (1) {
    sel = UI_MenuLoop("DEMO", demo_m, DEMO_ITEMS, sel);
    if (sel == 0)
      return;
    if (demo_f[sel]) {
      demo_f[sel]();
    }
  }
}

static void led_apply(bool r, bool g, bool b, bool w) {
  if (r) redLed.on(); else redLed.off();
  if (g) greenLed.on(); else greenLed.off();
  if (b) blueLed.on(); else blueLed.off();
  if (w) whiteLed.on(); else whiteLed.off();
}

static void led_all_off(void) {
  redLed.off();
  greenLed.off();
  blueLed.off();
  whiteLed.off();
}

static void led_test_activity(void) {
  static const char *labels[] = {
      "00 Return", "01 Red PF6", "02 Green PF7", "03 Blue PF8",
      "04 White PF9",
  };
  bool on[4] = {false, false, false, false};
  int sel = 0;
  uint8_t last_enter = 0;
  uint32_t lu = 0;
  bool dirty = true;

  led_all_off();
  while (1) {
    TosApi_Tick();
    keyManager.tick();

    if (keyManager._collisionA8.getState() == KEY_PRESSED) {
      sel = (sel + 1) % 5;
      dirty = true;
      JPDelay(2);
    }
    if (keyManager._collisionD0.getState() == KEY_PRESSED) {
      sel = (sel - 1 + 5) % 5;
      dirty = true;
      JPDelay(2);
    }

    uint8_t enter = keyManager._btnEnter.getState() == KEY_PRESSED;
    if (enter && !last_enter) {
      if (sel == 0) {
        led_all_off();
        return;
      }
      on[sel - 1] = !on[sel - 1];
      led_apply(on[0], on[1], on[2], on[3]);
      dirty = true;
    }
    last_enter = enter;

    if (dirty || (uint32_t)(HAL_GetTick() - lu) > 80U) {
      lu = HAL_GetTick();
      dirty = false;
      LCD_FLUSH({
        UI_DrawFrameTitle("LED TEST");
        PD_SetFont(FONT_ASCII_16);
        UI_DrawMenuCard(0, sel, 33, labels[0]);
        UI_DrawMenuBool(1, sel, 58, labels[1], on[0], false);
        UI_DrawMenuBool(2, sel, 83, labels[2], on[1], false);
        UI_DrawMenuBool(3, sel, 108, labels[3], on[2], false);
        UI_DrawMenuBool(4, sel, 133, labels[4], on[3], false);
        PD_DrawFooterCenter("ENTER", NULL, "UP/DOWN");
      });
    }
    TosApi_Tick();
    JPDelay(1);
  }
}
