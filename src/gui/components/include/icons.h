/**
 ******************************************************************************
 * @file    icons.h
 * @brief   Minimal title-bar icon asset.
 ******************************************************************************
 */

#pragma once
#include <stdint.h>

typedef struct {
  const uint8_t *bitmap;
  uint8_t width;
  uint8_t height;
  uint8_t bytes_per_row;
  int8_t x_offset;
  int8_t y_offset;
} IconBitmap;

typedef void (*IconPixelFn)(int x, int y, void *user);

static inline void icon_draw_bitmap_msb(const IconBitmap *icon, int left,
                                        int top, IconPixelFn put_pixel,
                                        void *user) {
  for (uint8_t y = 0; y < icon->height; ++y) {
    const uint8_t *row = icon->bitmap + (uint16_t)y * icon->bytes_per_row;
    for (uint8_t x = 0; x < icon->width; ++x) {
      if (row[x >> 3] & (uint8_t)(0x80u >> (x & 7))) {
        put_pixel(left + icon->x_offset + x, top + icon->y_offset + y, user);
      }
    }
  }
}

/* Title-bar ico icon (13x15 px, x_off=6, y_off=6). */
#define ICO_X_OFFSET 6
#define ICO_Y_OFFSET 6
#define ICO_W 13
#define ICO_H 15
#define ICO_BYTES_PER_ROW 2

static const uint8_t ico_bmp[15][2] = {
    {0xFF, 0xF8}, /* 00 ############# */
    {0xFF, 0xF8}, /* 01 ############# */
    {0xC0, 0x18}, /* 02 ##.........## */
    {0xFF, 0x18}, /* 03 ########...## */
    {0xC0, 0x18}, /* 04 ##.........## */
    {0xF8, 0x18}, /* 05 #####......## */
    {0xFF, 0x18}, /* 06 ########...## */
    {0xFF, 0x18}, /* 07 ########...## */
    {0xFF, 0x18}, /* 08 ########...## */
    {0xF8, 0x18}, /* 09 #####......## */
    {0xC0, 0x18}, /* 10 ##.........## */
    {0xC0, 0x18}, /* 11 ##.........## */
    {0xC0, 0x18}, /* 12 ##.........## */
    {0xFF, 0xF8}, /* 13 ############# */
    {0xFF, 0xF8}, /* 14 ############# */
};

static const IconBitmap ICON_ICO = {
    (const uint8_t *)ico_bmp, ICO_W, ICO_H, ICO_BYTES_PER_ROW,
    ICO_X_OFFSET, ICO_Y_OFFSET
};
