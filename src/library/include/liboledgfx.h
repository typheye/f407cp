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
void LibOledGfx_DrawText5x7(uint8_t *buffer, uint8_t x, uint8_t y,
                           const char *text);
void LibOledGfx_DrawText3x5(uint8_t *buffer, uint8_t x, uint8_t y,
                           const char *text);
void LibOledGfx_DrawDigitalClock(uint8_t *buffer, uint16_t year,
                                uint8_t month, uint8_t day,
                                const char *weekday, uint8_t hour,
                                uint8_t minute, uint8_t second);
void LibOledGfx_DrawDigitalClockWave(uint8_t *buffer, uint16_t year,
                                     uint8_t month, uint8_t day,
                                     const char *weekday, uint8_t hour,
                                     uint8_t minute, uint8_t second,
                                     uint8_t wave_phase);

#ifdef __cplusplus
}
#endif

#endif
