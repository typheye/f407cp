/**
 ******************************************************************************
 * @file    cust.c
 * @author  Typheye
 * @brief   ELF board-specific customization implementation.
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

#include "cust.h"

#include "manifest.h"
#include "stm32f4xx.h"

#define ELF_OLED_SCL_PIN 6U
#define ELF_OLED_SDA_PIN 7U
#define ELF_OLED_ADDRESS_PRIMARY 0x3CU
#define ELF_OLED_ADDRESS_SECONDARY 0x3DU

static void Cust_OledDelay(void) {
  for (volatile uint32_t i = 0U; i < 24U; ++i) {
    __NOP();
  }
}

static void Cust_OledSetScl(uint8_t high) {
  GPIOB->BSRR = high ? (1UL << ELF_OLED_SCL_PIN)
                     : (1UL << (ELF_OLED_SCL_PIN + 16U));
  Cust_OledDelay();
}

static void Cust_OledSetSda(uint8_t high) {
  GPIOB->BSRR = high ? (1UL << ELF_OLED_SDA_PIN)
                     : (1UL << (ELF_OLED_SDA_PIN + 16U));
  Cust_OledDelay();
}

static void Cust_OledStart(void) {
  Cust_OledSetSda(1U);
  Cust_OledSetScl(1U);
  Cust_OledSetSda(0U);
  Cust_OledSetScl(0U);
}

static void Cust_OledStop(void) {
  Cust_OledSetSda(0U);
  Cust_OledSetScl(1U);
  Cust_OledSetSda(1U);
}

static uint8_t Cust_OledWriteByte(uint8_t value) {
  for (uint8_t mask = 0x80U; mask != 0U; mask >>= 1U) {
    Cust_OledSetSda((value & mask) != 0U);
    Cust_OledSetScl(1U);
    Cust_OledSetScl(0U);
  }

  Cust_OledSetSda(1U);
  Cust_OledSetScl(1U);
  const uint8_t acknowledged =
      (GPIOB->IDR & (1UL << ELF_OLED_SDA_PIN)) == 0U;
  Cust_OledSetScl(0U);
  return acknowledged;
}

static uint8_t Cust_OledBegin(uint8_t address, uint8_t control) {
  Cust_OledStart();
  if (!Cust_OledWriteByte((uint8_t)(address << 1U)) ||
      !Cust_OledWriteByte(control)) {
    Cust_OledStop();
    return 0U;
  }
  return 1U;
}

static uint8_t Cust_OledClearAt(uint8_t address) {
  static const uint8_t setup[] = {
      0xAEU,                   /* Display off. */
      0x20U, 0x00U,            /* Horizontal addressing mode. */
      0x21U, 0x00U, 0x7FU,     /* Columns 0..127. */
      0x22U, 0x00U, 0x07U,     /* Pages 0..7. */
  };

  if (!Cust_OledBegin(address, 0x00U)) {
    return 0U;
  }
  for (uint32_t i = 0U; i < sizeof(setup); ++i) {
    if (!Cust_OledWriteByte(setup[i])) {
      Cust_OledStop();
      return 0U;
    }
  }
  Cust_OledStop();

  if (!Cust_OledBegin(address, 0x40U)) {
    return 0U;
  }
  for (uint32_t i = 0U; i < 1024U; ++i) {
    if (!Cust_OledWriteByte(0x00U)) {
      Cust_OledStop();
      return 0U;
    }
  }
  Cust_OledStop();
  return 1U;
}

static void Cust_OledForceBlack(void) {
  /* PB6/PB7 emulate an open-drain I2C bus before HAL is available. */
  GPIOB->OTYPER |= (1UL << ELF_OLED_SCL_PIN) | (1UL << ELF_OLED_SDA_PIN);
  GPIOB->OSPEEDR &= ~((3UL << (ELF_OLED_SCL_PIN * 2U)) |
                      (3UL << (ELF_OLED_SDA_PIN * 2U)));
  GPIOB->PUPDR &= ~((3UL << (ELF_OLED_SCL_PIN * 2U)) |
                    (3UL << (ELF_OLED_SDA_PIN * 2U)));
  GPIOB->PUPDR |= (1UL << (ELF_OLED_SCL_PIN * 2U)) |
                  (1UL << (ELF_OLED_SDA_PIN * 2U));
  GPIOB->MODER &= ~((3UL << (ELF_OLED_SCL_PIN * 2U)) |
                    (3UL << (ELF_OLED_SDA_PIN * 2U)));
  GPIOB->MODER |= (1UL << (ELF_OLED_SCL_PIN * 2U)) |
                  (1UL << (ELF_OLED_SDA_PIN * 2U));
  Cust_OledSetSda(1U);
  Cust_OledSetScl(1U);

  if (!Cust_OledClearAt(ELF_OLED_ADDRESS_PRIMARY)) {
    (void)Cust_OledClearAt(ELF_OLED_ADDRESS_SECONDARY);
  }
}

/* GPIO bootstrap — runs before any verification or TEE reads.
 * Hold external hardware in safe state until SBL takes over. */
void Cust_Setup(void) {
  RCC->AHB1ENR |= RCC_AHB1ENR_GPIOAEN | RCC_AHB1ENR_GPIOBEN |
                  RCC_AHB1ENR_GPIODEN | RCC_AHB1ENR_GPIOFEN;
  (void)RCC->AHB1ENR;

  /* BTN: input + pull-up */
  BTN_PORT->MODER &= ~(3UL << (BTN_PIN * 2U));
  BTN_PORT->PUPDR &= ~(3UL << (BTN_PIN * 2U));
  BTN_PORT->PUPDR |=  (1UL << (BTN_PIN * 2U));

  /* LCD RST high, BL off */
  GPIOD->MODER &= ~((3UL << (14U * 2U)) | (3UL << (13U * 2U)));
  GPIOD->MODER |=  ((1UL << (14U * 2U)) | (1UL << (13U * 2U)));
  GPIOD->BSRR = (1UL << 14U) | (1UL << (13U + 16U));

  /* Keep the four LEDs and PF10 low before switching them to outputs. */
  GPIOF->BSRR = ((1UL << 6U) | (1UL << 7U) | (1UL << 8U) |
                 (1UL << 9U) | (1UL << 10U)) << 16U;
  GPIOF->OTYPER &= ~((1UL << 6U) | (1UL << 7U) | (1UL << 8U) |
                     (1UL << 9U) | (1UL << 10U));
  GPIOF->MODER &= ~((3UL << (6U * 2U)) | (3UL << (7U * 2U)) |
                    (3UL << (8U * 2U)) | (3UL << (9U * 2U)) |
                    (3UL << (10U * 2U)));
  GPIOF->MODER |=  ((1UL << (6U * 2U)) | (1UL << (7U * 2U)) |
                    (1UL << (8U * 2U)) | (1UL << (9U * 2U)) |
                    (1UL << (10U * 2U)));

  Cust_OledForceBlack();
}

void Cust_Init(void)   { /* reserved */ }
void Cust_Finally(void) { /* reserved */ }
