#ifndef TOS_LCD_H
#define TOS_LCD_H

#include "stm32f4xx_hal.h"
#include <stdint.h>

#define LCD_WIDTH 240U
#define LCD_HEIGHT 240U
#define TILE_HEIGHT 60U

#define LCD_COLOR_BLACK 0x000000U
#define LCD_COLOR_WHITE 0xFFFFFFU
#define LCD_COLOR_RED 0xFF0000U
#define LCD_COLOR_GREEN 0x00FF00U
#define LCD_COLOR_BLUE 0x0000FFU
#define LCD_COLOR_GRAY 0x808080U
#define LCD_COLOR_CYAN 0x00FFFFU
#define LCD_COLOR_MAGENTA 0xFF00FFU
#define LCD_COLOR_YELLOW 0xFFFF00U

#ifdef __cplusplus
extern "C" {
#endif

void LCD_Init(void);
void LCD_FillScreen(uint32_t color);
void LCD_DrawPixel(int16_t x, int16_t y, uint32_t color);
void LCD_FillRect(int16_t x, int16_t y, int16_t w, int16_t h,
                  uint32_t color);
void LCD_Flush(void);
uint16_t *LCD_GetFrameBuffer(void);
void LCD_ClearFrameBuffer(uint32_t color);
void LCD_BeginTileRender(uint16_t y, uint16_t h);
void LCD_EndTileRender(void);
void LCD_FlushTiled(void (*render_cb)(void));
void LCD_FlushTiledBlocking(void (*render_cb)(void));
void LCD_EmergencyPrepare(void);
void LCD_UpdateAutoBrightness(void);
uint16_t LCD_RGB888ToRGB565(uint32_t rgb888);
uint16_t LCD_GetWidth(void);
uint16_t LCD_GetHeight(void);
uint16_t LCD_GetTileY(void);
uint16_t LCD_GetTileH(void);

#ifdef __cplusplus
}
#endif

#endif
