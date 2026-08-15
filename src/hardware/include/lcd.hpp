#ifndef TOS_LCD_HPP
#define TOS_LCD_HPP

#include "lcd.h"
#include "spi.h"
#include "tim.h"

class LCD {
public:
  LCD();
  void init();
  void fillScreen(uint32_t color);
  void drawPixel(uint16_t x, uint16_t y, uint32_t color);
  void fillRect(uint16_t x, uint16_t y, uint16_t w, uint16_t h,
                uint32_t color);
  void setBrightness(uint16_t value);
  uint16_t getBrightness() const { return _brightness; }
  void adjustBrightness(int16_t delta);
  uint16_t rgb888ToRgb565(uint32_t color) const;
  uint16_t *getFrameBuffer();
  void beginTileRender(uint16_t y, uint16_t h);
  void endTileRender();
  void flushTiled(void (*render_cb)(void));
  template <typename Render>
  void flushTiled(Render render) {
    if (!_initialized)
      return;
    for (uint16_t y = 0U; y < LCD_HEIGHT; y += TILE_HEIGHT) {
      beginTileRender(y, TILE_HEIGHT);
      render();
      endTileRender();
    }
  }
  uint16_t getTileY() const { return _tileY; }
  uint16_t getTileH() const { return _tileH; }

private:
  bool _initialized;
  uint16_t _brightness;
  uint16_t _tileY;
  uint16_t _tileH;

  void writeCommand(uint8_t command);
  void writeData(const uint8_t *data, uint16_t size);
  void writeData8(uint8_t data);
  void writeData16(uint16_t data);
  void setAddress(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1);
};

extern LCD boardLCD;

#define LCD_FLUSH(...)                                                        \
  do {                                                                        \
    boardLCD.flushTiled([&]() { __VA_ARGS__; });                              \
  } while (0)

#endif
