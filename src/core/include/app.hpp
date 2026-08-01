/**
 ******************************************************************************
 * @file    APP.hpp
 * @author  Typheye
 * @brief   APP interface.
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

#ifndef APP_HPP
#define APP_HPP

// ── Hardware headers ──────────────────────────────────────────
#include "include/buzzer.hpp"
#include "include/led.hpp"
#include "include/libvan.h"

#include "main.h"
#include "stm32f4xx_hal.h"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>

// ── APP class ─────────────────────────────────────────────────
class APP {
public:
  APP();
  ~APP();

  void init();
  void start();

private:
  bool _initialized;
  uint32_t _tickCount;
};

#ifdef __cplusplus
extern "C" {
#endif
void APP_Start(void);
#ifdef __cplusplus
}
#endif

#endif // APP_HPP
