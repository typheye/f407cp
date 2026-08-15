#include "include/liboledgfx.h"

#include <string.h>
#include <stdio.h>

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

static const uint8_t *glyph5x7(char ch) {
  static const uint8_t blank[5] = {0, 0, 0, 0, 0};
  static const uint8_t dash[5] = {0x08, 0x08, 0x08, 0x08, 0x08};
  static const uint8_t colon[5] = {0, 0x36, 0x36, 0, 0};
  static const uint8_t digits[10][5] = {
      {0x3E,0x51,0x49,0x45,0x3E}, {0x00,0x42,0x7F,0x40,0x00},
      {0x42,0x61,0x51,0x49,0x46}, {0x21,0x41,0x45,0x4B,0x31},
      {0x18,0x14,0x12,0x7F,0x10}, {0x27,0x45,0x45,0x45,0x39},
      {0x3C,0x4A,0x49,0x49,0x30}, {0x01,0x71,0x09,0x05,0x03},
      {0x36,0x49,0x49,0x49,0x36}, {0x06,0x49,0x49,0x29,0x1E}};
  static const uint8_t letters[26][5] = {
      {0x7E,0x11,0x11,0x11,0x7E}, {0x7F,0x49,0x49,0x49,0x36},
      {0x3E,0x41,0x41,0x41,0x22}, {0x7F,0x41,0x41,0x22,0x1C},
      {0x7F,0x49,0x49,0x49,0x41}, {0x7F,0x09,0x09,0x09,0x01},
      {0x3E,0x41,0x49,0x49,0x7A}, {0x7F,0x08,0x08,0x08,0x7F},
      {0x00,0x41,0x7F,0x41,0x00}, {0x20,0x40,0x41,0x3F,0x01},
      {0x7F,0x08,0x14,0x22,0x41}, {0x7F,0x40,0x40,0x40,0x40},
      {0x7F,0x02,0x0C,0x02,0x7F}, {0x7F,0x04,0x08,0x10,0x7F},
      {0x3E,0x41,0x41,0x41,0x3E}, {0x7F,0x09,0x09,0x09,0x06},
      {0x3E,0x41,0x51,0x21,0x5E}, {0x7F,0x09,0x19,0x29,0x46},
      {0x46,0x49,0x49,0x49,0x31}, {0x01,0x01,0x7F,0x01,0x01},
      {0x3F,0x40,0x40,0x40,0x3F}, {0x1F,0x20,0x40,0x20,0x1F},
      {0x7F,0x20,0x18,0x20,0x7F}, {0x63,0x14,0x08,0x14,0x63},
      {0x07,0x08,0x70,0x08,0x07}, {0x61,0x51,0x49,0x45,0x43}};
  if (ch >= '0' && ch <= '9') return digits[ch - '0'];
  if (ch >= 'a' && ch <= 'z') ch = (char)(ch - 'a' + 'A');
  if (ch >= 'A' && ch <= 'Z') return letters[ch - 'A'];
  if (ch == '-') return dash;
  if (ch == ':') return colon;
  return blank;
}

void LibOledGfx_DrawText5x7(uint8_t *buffer, uint8_t x, uint8_t y,
                           const char *text) {
  if (buffer == 0 || text == 0) return;
  while (*text != '\0' && x < LIBOLEDGFX_WIDTH) {
    const uint8_t *glyph = glyph5x7(*text++);
    for (uint8_t gx = 0U; gx < 5U; ++gx) {
      for (uint8_t gy = 0U; gy < 7U; ++gy) {
        if ((glyph[gx] & (1U << gy)) != 0U)
          LibOledGfx_FillRect(buffer, (uint8_t)(x + gx), (uint8_t)(y + gy),
                              1U, 1U, 1U);
      }
    }
    x = (uint8_t)(x + 6U);
  }
}

static void drawSegment(uint8_t *buffer, uint8_t x, uint8_t y,
                        uint8_t segment) {
  const uint8_t t = 2U;
  if (segment == 0U) LibOledGfx_FillRect(buffer, x + t, y, 10U, t, 1U);
  if (segment == 1U) LibOledGfx_FillRect(buffer, x + 12U, y + t, t, 11U, 1U);
  if (segment == 2U) LibOledGfx_FillRect(buffer, x + 12U, y + 15U, t, 11U, 1U);
  if (segment == 3U) LibOledGfx_FillRect(buffer, x + t, y + 26U, 10U, t, 1U);
  if (segment == 4U) LibOledGfx_FillRect(buffer, x, y + 15U, t, 11U, 1U);
  if (segment == 5U) LibOledGfx_FillRect(buffer, x, y + t, t, 11U, 1U);
  if (segment == 6U) LibOledGfx_FillRect(buffer, x + t, y + 13U, 10U, t, 1U);
}

static void drawDigit(uint8_t *buffer, uint8_t x, uint8_t y, uint8_t digit) {
  static const uint8_t masks[10] = {
      0x3FU, 0x06U, 0x5BU, 0x4FU, 0x66U,
      0x6DU, 0x7DU, 0x07U, 0x7FU, 0x6FU};
  if (digit > 9U) return;
  for (uint8_t segment = 0U; segment < 7U; ++segment)
    if ((masks[digit] & (1U << segment)) != 0U)
      drawSegment(buffer, x, y, segment);
}

void LibOledGfx_DrawDigitalClock(uint8_t *buffer, uint16_t year,
                                uint8_t month, uint8_t day,
                                const char *weekday, uint8_t hour,
                                uint8_t minute, uint8_t second) {
  LibOledGfx_DrawDigitalClockWave(buffer, year, month, day, weekday, hour,
                                  minute, second, 0U);
}

void LibOledGfx_DrawDigitalClockWave(uint8_t *buffer, uint16_t year,
                                    uint8_t month, uint8_t day,
                                    const char *weekday, uint8_t hour,
                                    uint8_t minute, uint8_t second,
                                    uint8_t wave_phase) {
  char date[24];
  LibOledGfx_Clear(buffer, 0U);
  snprintf(date, sizeof(date), "%04u-%02u-%02u %s", year, month, day,
           weekday ? weekday : "");
  size_t date_len = strlen(date);
  uint8_t date_x =
      date_len * 6U < 128U ? (uint8_t)((128U - date_len * 6U) / 2U) : 0U;
  LibOledGfx_DrawText5x7(buffer, date_x, 0U, date);
  LibOledGfx_FillRect(buffer, 0U, 10U, 128U, 1U, 1U);

  const uint8_t values[6] = {hour / 10U, hour % 10U, minute / 10U,
                             minute % 10U, second / 10U, second % 10U};
  const uint8_t positions[6] = {4U, 22U, 46U, 64U, 88U, 106U};
  for (uint8_t i = 0U; i < 6U; ++i)
    drawDigit(buffer, positions[i], 16U, values[i]);
  LibOledGfx_FillRect(buffer, 41U, 23U, 3U, 3U, 1U);
  LibOledGfx_FillRect(buffer, 41U, 36U, 3U, 3U, 1U);
  LibOledGfx_FillRect(buffer, 83U, 23U, 3U, 3U, 1U);
  LibOledGfx_FillRect(buffer, 83U, 36U, 3U, 3U, 1U);

  static const int8_t wave[16] = {0, 1, 2, 2, 3, 2, 2, 1,
                                  0, -1, -2, -2, -3, -2, -2, -1};
  for (uint8_t x = 0U; x < LIBOLEDGFX_WIDTH; x += 2U) {
    uint8_t idx = (uint8_t)((x / 2U + wave_phase) & 0x0FU);
    int16_t y = (int16_t)59 + wave[idx];
    if (y < 54) y = 54;
    if (y > 63) y = 63;
    LibOledGfx_FillRect(buffer, x, (uint8_t)y, 2U, 1U, 1U);
    if ((x & 0x06U) == 0U && y + 1 <= 63) {
      LibOledGfx_FillRect(buffer, x, (uint8_t)(y + 1), 2U, 1U, 1U);
    }
  }
}
