#include "include/liboledgfx.h"

#include <string.h>

void LibOledGfx_Clear(uint8_t *buffer, uint8_t color) {
  if (buffer == 0)
    return;
  memset(buffer, color ? 0xFF : 0x00, LIBOLEDGFX_BUFFER_SIZE);
}

void LibOledGfx_FillRect(uint8_t *buffer, uint8_t x, uint8_t y,
                        uint8_t width, uint8_t height, uint8_t color) {
  if (buffer == 0 || x >= LIBOLEDGFX_WIDTH || y >= LIBOLEDGFX_HEIGHT)
    return;

  uint16_t xEnd = (uint16_t)x + width;
  uint16_t yEnd = (uint16_t)y + height;
  if (xEnd > LIBOLEDGFX_WIDTH)
    xEnd = LIBOLEDGFX_WIDTH;
  if (yEnd > LIBOLEDGFX_HEIGHT)
    yEnd = LIBOLEDGFX_HEIGHT;

  for (uint16_t py = y; py < yEnd; ++py) {
    const uint8_t mask = (uint8_t)(1U << (py & 7U));
    for (uint16_t px = x; px < xEnd; ++px) {
      uint8_t *pixelByte = &buffer[px + (py / 8U) * LIBOLEDGFX_WIDTH];
      if (color)
        *pixelByte |= mask;
      else
        *pixelByte &= (uint8_t)~mask;
    }
  }
}

void LibOledGfx_DrawCheckerboard8x4(uint8_t *buffer) {
  LibOledGfx_Clear(buffer, 0U);
  for (uint8_t row = 0U; row < 4U; ++row) {
    for (uint8_t column = 0U; column < 8U; ++column) {
      LibOledGfx_FillRect(buffer, (uint8_t)(column * 16U),
                         (uint8_t)(row * 16U), 16U, 16U,
                         (uint8_t)((row + column) & 1U));
    }
  }
}
