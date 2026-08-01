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

extern USART boardSerial;
extern LED boardLed;
extern Buzzer buzzer1;

void TOS::init() {
  SysDram_Init();
  boardSerial.init();

  boardLed.init();

  buzzer1.init();
  JPDelay(50);

  _initialized = true;

  LOG_I("MAIN", "System initialized, CPU:168MHz");
  SysDram_LogStats();
}
