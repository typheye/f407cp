#include "include/lcd.hpp"

#include "library/include/libpd.h"
#include "library/include/libemo.h"
#include "library/include/libdly.h"
#include "rtc.h"

extern "C" void SysUI_DebugOverlayBeginFrame(void);
extern "C" void SysUI_DebugOverlayEndFrame(void);
extern "C" void SysUI_DebugOverlayDraw(void);
extern void lcd_dma_yield(void);

static volatile uint8_t lcd_debug_overlay_suppressed = 0;

namespace {
constexpr uint16_t kDefaultBrightness = 700U;
constexpr uint32_t kBrightnessMagic = 0x42524954U;
constexpr uint32_t kBackupMagicRegister = RTC_BKP_DR1;
constexpr uint32_t kBackupValueRegister = RTC_BKP_DR2;
uint16_t tileBuffer[LCD_WIDTH * TILE_HEIGHT];

void configureControlPins() {
  __HAL_RCC_GPIOD_CLK_ENABLE();
  GPIO_InitTypeDef gpio{};
  gpio.Pin = GPIO_PIN_11 | GPIO_PIN_12 | GPIO_PIN_14;
  gpio.Mode = GPIO_MODE_OUTPUT_PP;
  gpio.Pull = GPIO_NOPULL;
  gpio.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
  HAL_GPIO_Init(GPIOD, &gpio);
  HAL_GPIO_WritePin(GPIOD, GPIO_PIN_11 | GPIO_PIN_14, GPIO_PIN_SET);
}
} // namespace

LCD boardLCD;

LCD::LCD()
    : _initialized(false), _autoBrightness(false), _sleeping(false),
      _rotation(0U), _brightness(kDefaultBrightness),
      _sleep_restore_brightness(kDefaultBrightness), _tileY(0U),
      _tileH(TILE_HEIGHT) {}

uint16_t LCD::rgb888ToRgb565(uint32_t color) const {
  return static_cast<uint16_t>(((color >> 8U) & 0xF800U) |
                               ((color >> 5U) & 0x07E0U) |
                               ((color >> 3U) & 0x001FU));
}

void LCD::writeCommand(uint8_t command) {
  HAL_GPIO_WritePin(GPIOD, GPIO_PIN_12, GPIO_PIN_RESET);
  HAL_GPIO_WritePin(GPIOD, GPIO_PIN_11, GPIO_PIN_RESET);
  (void)HAL_SPI_Transmit(&hspi1, &command, 1U, 100U);
  HAL_GPIO_WritePin(GPIOD, GPIO_PIN_11, GPIO_PIN_SET);
}

void LCD::writeData(const uint8_t *data, uint16_t size) {
  HAL_GPIO_WritePin(GPIOD, GPIO_PIN_12, GPIO_PIN_SET);
  HAL_GPIO_WritePin(GPIOD, GPIO_PIN_11, GPIO_PIN_RESET);
  (void)HAL_SPI_Transmit(&hspi1, const_cast<uint8_t *>(data), size, 500U);
  HAL_GPIO_WritePin(GPIOD, GPIO_PIN_11, GPIO_PIN_SET);
}

void LCD::writeData8(uint8_t data) { writeData(&data, 1U); }

void LCD::writeData16(uint16_t data) {
  uint8_t bytes[] = {static_cast<uint8_t>(data >> 8U),
                     static_cast<uint8_t>(data)};
  writeData(bytes, sizeof(bytes));
}

void LCD::setAddress(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1) {
  if (_rotation == 0U) {
    const uint16_t fx0 = static_cast<uint16_t>(LCD_WIDTH - 1U - x1);
    const uint16_t fy0 = static_cast<uint16_t>(LCD_HEIGHT - 1U - y1);
    const uint16_t fx1 = static_cast<uint16_t>(LCD_WIDTH - 1U - x0);
    const uint16_t fy1 = static_cast<uint16_t>(LCD_HEIGHT - 1U - y0);
    x0 = fx0;
    y0 = fy0;
    x1 = fx1;
    y1 = fy1;
  }
  writeCommand(0x2AU);
  writeData16(x0);
  writeData16(x1);
  writeCommand(0x2BU);
  writeData16(y0);
  writeData16(y1);
  writeCommand(0x2CU);
}

void LCD::init() {
  configureControlPins();

  /* Keep the SBL framebuffer/logo handoff: do not hardware-reset or clear the
   * panel here. Reapply the complete TOS ST7789 setup sequence, while using
   * the tested native CW MADCTL plus software window transform. */
  writeCommand(0x3AU);
  writeData8(0x55U);
  writeCommand(0x36U);
  writeData8(0x60U);
  writeCommand(0xB2U);
  const uint8_t porch[] = {0x0CU, 0x0CU, 0x00U, 0x33U, 0x33U};
  writeData(porch, sizeof(porch));
  writeCommand(0xB7U); writeData8(0x35U);
  writeCommand(0xBBU); writeData8(0x19U);
  writeCommand(0xC0U); writeData8(0x2CU);
  writeCommand(0xC2U); writeData8(0x01U);
  writeCommand(0xC3U); writeData8(0x12U);
  writeCommand(0xC4U); writeData8(0x20U);
  writeCommand(0xC6U); writeData8(0x0FU);
  writeCommand(0xD0U);
  const uint8_t power[] = {0xA4U, 0xA1U};
  writeData(power, sizeof(power));
  writeCommand(0xE0U);
  const uint8_t gammaP[] = {0xD0U,0x04U,0x0DU,0x11U,0x13U,0x2BU,0x3FU,
                            0x54U,0x4CU,0x18U,0x0DU,0x0BU,0x1FU,0x23U};
  writeData(gammaP, sizeof(gammaP));
  writeCommand(0xE1U);
  const uint8_t gammaN[] = {0xD0U,0x04U,0x0CU,0x11U,0x13U,0x2CU,0x3FU,
                            0x44U,0x51U,0x2FU,0x1FU,0x1FU,0x20U,0x23U};
  writeData(gammaN, sizeof(gammaN));
  writeCommand(0x21U);
  writeCommand(0x29U);
  JPDelay(100U);

  _initialized = true;
  if (HAL_RTCEx_BKUPRead(&hrtc, kBackupMagicRegister) == kBrightnessMagic) {
    const uint32_t stored = HAL_RTCEx_BKUPRead(&hrtc, kBackupValueRegister);
    if (stored <= 1000U) {
      _brightness = static_cast<uint16_t>(stored);
    }
  }
  setBrightness(_brightness);
}

void LCD::setBrightness(uint16_t value) {
  if (value > 1000U)
    value = 1000U;
  _brightness = value;
  if (!_sleeping) {
    applyBrightness(value);
  }

  HAL_PWR_EnableBkUpAccess();
  HAL_RTCEx_BKUPWrite(&hrtc, kBackupMagicRegister, kBrightnessMagic);
  HAL_RTCEx_BKUPWrite(&hrtc, kBackupValueRegister, value);
}

void LCD::applyBrightness(uint16_t value) {
  (void)HAL_TIM_PWM_Start(&htim4, TIM_CHANNEL_2);
  const uint32_t period = __HAL_TIM_GET_AUTORELOAD(&htim4) + 1U;
  const uint32_t compare =
      value >= 1000U ? period : (static_cast<uint32_t>(value) * period) / 1000U;
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_2, compare);
}

void LCD::adjustBrightness(int16_t delta) {
  int32_t next = static_cast<int32_t>(_brightness) + delta;
  if (next < 100)
    next = 100;
  if (next > 1000)
    next = 1000;
  setBrightness(static_cast<uint16_t>(next));
}

void LCD::setAutoBrightness(bool enabled) {
  _autoBrightness = enabled;
}

void LCD::setRotation(uint8_t rotation) {
  /* Restore the stable 2-mode compatibility path. */
  _rotation = static_cast<uint8_t>(rotation & 0x01U);
}

void LCD::sleep() {
  if (_sleeping)
    return;
  _sleep_restore_brightness = _brightness ? _brightness : kDefaultBrightness;
  _sleeping = true;
  applyBrightness(0U);
}

void LCD::wake() {
  if (!_sleeping)
    return;
  _sleeping = false;
  applyBrightness(_sleep_restore_brightness ? _sleep_restore_brightness
                                            : kDefaultBrightness);
}

void LCD::updateAutoBrightness() {
  /* This board uses manual TIM4 backlight control. Keep the upstream launcher
   * hook callable without changing the user-selected brightness. */
}

void LCD::fillRect(uint16_t x, uint16_t y, uint16_t w, uint16_t h,
                   uint32_t color) {
  if (!_initialized || x >= LCD_WIDTH || y >= LCD_HEIGHT || w == 0U || h == 0U)
    return;
  if (x + w > LCD_WIDTH)
    w = static_cast<uint16_t>(LCD_WIDTH - x);
  if (y + h > LCD_HEIGHT)
    h = static_cast<uint16_t>(LCD_HEIGHT - y);
  setAddress(x, y, static_cast<uint16_t>(x + w - 1U),
             static_cast<uint16_t>(y + h - 1U));
  const uint16_t pixel = rgb888ToRgb565(color);
  uint8_t block[128];
  for (uint32_t i = 0U; i < sizeof(block); i += 2U) {
    block[i] = static_cast<uint8_t>(pixel >> 8U);
    block[i + 1U] = static_cast<uint8_t>(pixel);
  }
  HAL_GPIO_WritePin(GPIOD, GPIO_PIN_12, GPIO_PIN_SET);
  HAL_GPIO_WritePin(GPIOD, GPIO_PIN_11, GPIO_PIN_RESET);
  uint32_t remaining = static_cast<uint32_t>(w) * h;
  while (remaining != 0U) {
    const uint16_t count = remaining > 64U ? 64U : static_cast<uint16_t>(remaining);
    (void)HAL_SPI_Transmit(&hspi1, block, static_cast<uint16_t>(count * 2U),
                           500U);
    remaining -= count;
  }
  HAL_GPIO_WritePin(GPIOD, GPIO_PIN_11, GPIO_PIN_SET);
}

void LCD::fillScreen(uint32_t color) {
  fillRect(0U, 0U, LCD_WIDTH, LCD_HEIGHT, color);
}

void LCD::drawPixel(uint16_t x, uint16_t y, uint32_t color) {
  fillRect(x, y, 1U, 1U, color);
}

uint16_t *LCD::getFrameBuffer() { return tileBuffer; }

void LCD::beginTileRender(uint16_t y, uint16_t h) {
  if (y >= LCD_HEIGHT)
    y = LCD_HEIGHT - 1U;
  if (h == 0U)
    h = 1U;
  if (h > TILE_HEIGHT)
    h = TILE_HEIGHT;
  if (y + h > LCD_HEIGHT)
    h = static_cast<uint16_t>(LCD_HEIGHT - y);
  _tileY = y;
  _tileH = h;
  if (y == 0U && !lcd_debug_overlay_suppressed) {
    SysUI_DebugOverlayBeginFrame();
  }
  PD_SetTileWindow(y, h);
  EMO_SetTileWindow(y, h);
  for (uint32_t i = 0U; i < static_cast<uint32_t>(LCD_WIDTH) * h; ++i)
    tileBuffer[i] = 0U;
}

void LCD::endTileRender() {
  if (!_initialized)
    return;
  const uint32_t pixels = static_cast<uint32_t>(LCD_WIDTH) * _tileH;
  if (!lcd_debug_overlay_suppressed) {
    SysUI_DebugOverlayDraw();
  }
  for (uint32_t i = 0U; i < pixels; ++i) {
    const uint16_t value = tileBuffer[i];
    tileBuffer[i] = static_cast<uint16_t>((value << 8U) | (value >> 8U));
  }
  if (_rotation == 0U) {
    for (uint32_t left = 0U, right = pixels - 1U; left < right; ++left, --right) {
      const uint16_t value = tileBuffer[left];
      tileBuffer[left] = tileBuffer[right];
      tileBuffer[right] = value;
    }
  }
  setAddress(0U, _tileY, LCD_WIDTH - 1U,
             static_cast<uint16_t>(_tileY + _tileH - 1U));
  HAL_GPIO_WritePin(GPIOD, GPIO_PIN_12, GPIO_PIN_SET);
  HAL_GPIO_WritePin(GPIOD, GPIO_PIN_11, GPIO_PIN_RESET);
  HAL_StatusTypeDef st = HAL_SPI_Transmit_DMA(
      &hspi1, reinterpret_cast<uint8_t *>(tileBuffer),
      static_cast<uint16_t>(pixels * 2U));
  if (st == HAL_OK) {
    uint32_t timeout = HAL_GetTick() + 120U;
    while (HAL_SPI_GetState(&hspi1) != HAL_SPI_STATE_READY) {
      if ((int32_t)(HAL_GetTick() - timeout) >= 0) {
        (void)HAL_SPI_Abort(&hspi1);
        break;
      }
      lcd_dma_yield();
    }
  } else {
    (void)HAL_SPI_Transmit(&hspi1, reinterpret_cast<uint8_t *>(tileBuffer),
                           static_cast<uint16_t>(pixels * 2U), 1000U);
  }
  HAL_GPIO_WritePin(GPIOD, GPIO_PIN_11, GPIO_PIN_SET);
  if ((_tileY + _tileH) >= LCD_HEIGHT && !lcd_debug_overlay_suppressed) {
    SysUI_DebugOverlayEndFrame();
  }
}

void LCD::flushTiled(void (*render_cb)(void)) {
  if (!_initialized || render_cb == nullptr)
    return;
  for (uint16_t y = 0U; y < LCD_HEIGHT; y += TILE_HEIGHT) {
    beginTileRender(y, TILE_HEIGHT);
    render_cb();
    endTileRender();
  }
}

extern "C" {
void LCD_Init(void) { boardLCD.init(); }
void LCD_FillScreen(uint32_t color) { boardLCD.fillScreen(color); }
void LCD_DrawPixel(int16_t x, int16_t y, uint32_t color) {
  if (x >= 0 && y >= 0)
    boardLCD.drawPixel(static_cast<uint16_t>(x), static_cast<uint16_t>(y), color);
}
void LCD_FillRect(int16_t x, int16_t y, int16_t w, int16_t h, uint32_t color) {
  if (x >= 0 && y >= 0 && w > 0 && h > 0)
    boardLCD.fillRect(static_cast<uint16_t>(x), static_cast<uint16_t>(y),
                      static_cast<uint16_t>(w), static_cast<uint16_t>(h), color);
}
void LCD_Flush(void) { boardLCD.endTileRender(); }
uint16_t *LCD_GetFrameBuffer(void) { return boardLCD.getFrameBuffer(); }
void LCD_ClearFrameBuffer(uint32_t color) {
  const uint16_t value = boardLCD.rgb888ToRgb565(color);
  for (uint32_t i = 0U; i < LCD_WIDTH * TILE_HEIGHT; ++i)
    tileBuffer[i] = value;
}
void LCD_BeginTileRender(uint16_t y, uint16_t h) { boardLCD.beginTileRender(y, h); }
void LCD_EndTileRender(void) { boardLCD.endTileRender(); }
void LCD_FlushTiled(void (*render_cb)(void)) { boardLCD.flushTiled(render_cb); }
void LCD_FlushTiledBlocking(void (*render_cb)(void)) { boardLCD.flushTiled(render_cb); }
void LCD_EmergencyPrepare(void) {
  if (boardLCD.getBrightness() < 700U) {
    boardLCD.setBrightness(700U);
  }
}
void LCD_UpdateAutoBrightness(void) { boardLCD.updateAutoBrightness(); }
void LCD_SetDebugOverlaySuppressed(uint8_t suppressed) {
  lcd_debug_overlay_suppressed = suppressed ? 1U : 0U;
}
uint16_t LCD_RGB888ToRGB565(uint32_t color) { return boardLCD.rgb888ToRgb565(color); }
uint16_t LCD_GetWidth(void) { return LCD_WIDTH; }
uint16_t LCD_GetHeight(void) { return LCD_HEIGHT; }
uint16_t LCD_GetTileY(void) { return boardLCD.getTileY(); }
uint16_t LCD_GetTileH(void) { return boardLCD.getTileH(); }
}
