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
#include "core/sys/include/syswatchdog.h"
#include "gui/include/sysui.hpp"
#include "hardware/include/cdc_bridge.h"
#include "hardware/include/key.hpp"
#include "hardware/include/lcd.hpp"
#include "hardware/include/secondary_clock.hpp"
#include "library/include/libdly.h"
#include "manifest.h"
#include "rtc.h"

extern "C" {}

extern LED boardLed;
extern Buzzer buzzer1;

void APP::init() {

  boardLed.init();
  redLed.init();
  greenLed.init();
  blueLed.init();
  whiteLed.init();

  keyManager.init();

  buzzer1.init();
  JPDelay(50);

  SysWatchdog_Init();
  boardLCD.init();
  SysUI::init();
  CDC_Bridge_Start();

  _initialized = true;

  /* ELF left the secondary panel off and cleared. Enable it only after the
   * complete SYSTEM UI and transport stack are ready. */
  SecondaryClock_Init();

  LOG_I("MAIN", "System initialized, CPU:168MHz");
}
