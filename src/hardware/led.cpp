/**
 ******************************************************************************
 * @file    led.cpp
 * @author  Typheye
 * @brief   Led implementation.
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

#include "include/led.hpp"
#include "library/include/libdly.h"

LED::LED(GPIO_TypeDef *port, uint16_t pin, bool polarity)
    : _port(port), _pin(pin), _polarity(polarity) {}

void LED::init(void) { off(); }

void LED::on(void) {
  if (_polarity) {

    HAL_GPIO_WritePin(_port, _pin, GPIO_PIN_SET);
  } else {

    HAL_GPIO_WritePin(_port, _pin, GPIO_PIN_RESET);
  }
}

void LED::off(void) {
  if (_polarity) {

    HAL_GPIO_WritePin(_port, _pin, GPIO_PIN_RESET);
  } else {

    HAL_GPIO_WritePin(_port, _pin, GPIO_PIN_SET);
  }
}

void LED::toggle(void) { HAL_GPIO_TogglePin(_port, _pin); }

void LED::blink(uint32_t delay_ms) {
  on();
  JPDelay(delay_ms);
  off();
  JPDelay(delay_ms);
}

LED boardLed(GPIOC, GPIO_PIN_13, false);
LED redLed(GPIOF, GPIO_PIN_6, true);
LED greenLed(GPIOF, GPIO_PIN_7, true);
LED blueLed(GPIOF, GPIO_PIN_8, true);
LED whiteLed(GPIOF, GPIO_PIN_9, true);
