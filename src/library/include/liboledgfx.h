#ifndef LIBOLEDGFX_H
#define LIBOLEDGFX_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define LIBOLEDGFX_WIDTH 128U
#define LIBOLEDGFX_HEIGHT 64U
#define LIBOLEDGFX_BUFFER_SIZE (LIBOLEDGFX_WIDTH * LIBOLEDGFX_HEIGHT / 8U)

void LibOledGfx_Clear(uint8_t *buffer, uint8_t color);
void LibOledGfx_FillRect(uint8_t *buffer, uint8_t x, uint8_t y,
                        uint8_t width, uint8_t height, uint8_t color);
void LibOledGfx_DrawCheckerboard8x4(uint8_t *buffer);

#ifdef __cplusplus
}
#endif

#endif
