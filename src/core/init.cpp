/**
 ******************************************************************************
 * @file    init.cpp
 * @author  Typheye
 * @brief   Core startup orchestration implementation.
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

#include "include/init.hpp"
#include "library/include/libdly.h"
#include "manifest.h"

extern "C" {}

extern LED boardLed;
extern Buzzer buzzer1;

void APP::init() {

  boardLed.init();
  redLed.init();
  greenLed.init();
  blueLed.init();
  whiteLed.init();

  key1.init();
  key2.init();
  key3.init();
  key4.init();

  buzzer1.init();
  JPDelay(50);

  static uint8_t oledBuffer[LIBOLEDGFX_BUFFER_SIZE];
  if (oled.init()) {
    LibOledGfx_Clear(oledBuffer, 0U);
    bool frameReady = oled.display(oledBuffer, sizeof(oledBuffer));
    if (frameReady) {
      LibOledGfx_DrawCheckerboard8x4(oledBuffer);
      frameReady = oled.display(oledBuffer, sizeof(oledBuffer));
    }
    if (frameReady && oled.setDisplayOn(true)) {
      LOG_I("OLED", "SSD1315 ready at 0x%02X", oled.address());
    } else {
      (void)oled.setDisplayOn(false);
      LOG_W("OLED", "SSD1315 frame initialization failed");
    }
  } else {
    LOG_W("OLED", "SSD1315 not found at 0x3C/0x3D");
  }

  _initialized = true;

  LOG_I("MAIN", "System initialized, CPU:168MHz");
}
