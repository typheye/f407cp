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
#include "library/include/libdly.h"
#include "library/include/libui.h"


extern KeyManager keyManager;
extern LCD boardLCD;

#define DEMO_ITEMS 4
static const char *demo_m[DEMO_ITEMS] = {
    "00 Return", "01 Key Test", "02 I2C Scan", "03 3D Path Tracer",
};
static void (*demo_f[DEMO_ITEMS])(void) = {
    NULL,
    key_test_activity,
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
