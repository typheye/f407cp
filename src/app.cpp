/**
 ******************************************************************************
 * @file    app.cpp
 * @author  Typheye
 * @brief   App implementation.
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

#include "core/include/app.hpp"
#include "library/include/libdly.h"

APP::APP() : _initialized(false), _tickCount(0) {}

void APP::start() {
  if (!_initialized)
    init();

  while (1) {
    JPDelay(10);
  }
}

APP::~APP() {}

extern "C" void APP_Start(void) {
  APP os;
  os.init();
  os.start();
}
