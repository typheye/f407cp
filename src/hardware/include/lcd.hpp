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
  void setAutoBrightness(bool enabled);
  bool getAutoBrightness() const { return _autoBrightness; }
  void setRotation(uint8_t rotation);
  uint8_t getRotation() const { return _rotation; }
  void sleep();
  void wake();
  bool isSleeping() const { return _sleeping; }
  void updateAutoBrightness();
  uint16_t rgb888ToRgb565(uint32_t color) const;
  uint16_t *getFrameBuffer();
  void beginTileRender(uint16_t y, uint16_t h);
  void beginTileRenderVideo(uint16_t y, uint16_t h);
  void endTileRender();
  void endTileRenderVideo();
  void flushTiled(void (*render_cb)(void));
  template <typename Render>
  void flushTiled(Render render) {
    if (!_initialized || _sleeping)
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
  bool _autoBrightness;
  bool _sleeping;
  uint8_t _rotation;
  uint16_t _brightness;
  uint16_t _sleep_restore_brightness;
  uint16_t _tileY;
  uint16_t _tileH;

  void writeCommand(uint8_t command);
  void writeData(const uint8_t *data, uint16_t size);
  void writeData8(uint8_t data);
  void writeData16(uint16_t data);
  void setAddress(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1);
  void applyBrightness(uint16_t value);
};

extern LCD boardLCD;

#define LCD_FLUSH(...)                                                        \
  do {                                                                        \
    boardLCD.flushTiled([&]() { __VA_ARGS__; });                              \
  } while (0)

#endif
