#include "include/lcd.hpp"

#include "library/include/libpd.h"
#include "rtc.h"

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
    : _initialized(false), _brightness(kDefaultBrightness), _tileY(0U),
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
  const uint16_t fx0 = static_cast<uint16_t>(LCD_WIDTH - 1U - x1);
  const uint16_t fy0 = static_cast<uint16_t>(LCD_HEIGHT - 1U - y1);
  const uint16_t fx1 = static_cast<uint16_t>(LCD_WIDTH - 1U - x0);
  const uint16_t fy1 = static_cast<uint16_t>(LCD_HEIGHT - 1U - y0);
  writeCommand(0x2AU);
  writeData16(fx0);
  writeData16(fx1);
  writeCommand(0x2BU);
  writeData16(fy0);
  writeData16(fy1);
  writeCommand(0x2CU);
}

void LCD::init() {
  configureControlPins();

  /* SBL already initialized the controller. Reassert only the format and the
   * known-good native CW mode; the software window transform supplies the
   * project's logical CCW orientation without the panel offset bug. */
  writeCommand(0x3AU);
  writeData8(0x55U);
  writeCommand(0x36U);
  writeData8(0x60U);
  writeCommand(0x21U);
  writeCommand(0x29U);

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
  (void)HAL_TIM_PWM_Start(&htim4, TIM_CHANNEL_2);
  const uint32_t period = __HAL_TIM_GET_AUTORELOAD(&htim4) + 1U;
  const uint32_t compare =
      value >= 1000U ? period : (static_cast<uint32_t>(value) * period) / 1000U;
  __HAL_TIM_SET_COMPARE(&htim4, TIM_CHANNEL_2, compare);

  HAL_PWR_EnableBkUpAccess();
  HAL_RTCEx_BKUPWrite(&hrtc, kBackupMagicRegister, kBrightnessMagic);
  HAL_RTCEx_BKUPWrite(&hrtc, kBackupValueRegister, value);
}

void LCD::adjustBrightness(int16_t delta) {
  int32_t next = static_cast<int32_t>(_brightness) + delta;
  if (next < 100)
    next = 100;
  if (next > 1000)
    next = 1000;
  setBrightness(static_cast<uint16_t>(next));
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
  if (y + h > LCD_HEIGHT)
    h = static_cast<uint16_t>(LCD_HEIGHT - y);
  _tileY = y;
  _tileH = h;
  PD_SetTileWindow(y, h);
  for (uint32_t i = 0U; i < static_cast<uint32_t>(LCD_WIDTH) * h; ++i)
    tileBuffer[i] = 0U;
}

void LCD::endTileRender() {
  if (!_initialized)
    return;
  const uint32_t pixels = static_cast<uint32_t>(LCD_WIDTH) * _tileH;
  for (uint32_t i = 0U; i < pixels; ++i) {
    const uint16_t value = tileBuffer[i];
    tileBuffer[i] = static_cast<uint16_t>((value << 8U) | (value >> 8U));
  }
  for (uint32_t left = 0U, right = pixels - 1U; left < right; ++left, --right) {
    const uint16_t value = tileBuffer[left];
    tileBuffer[left] = tileBuffer[right];
    tileBuffer[right] = value;
  }
  setAddress(0U, _tileY, LCD_WIDTH - 1U,
             static_cast<uint16_t>(_tileY + _tileH - 1U));
  HAL_GPIO_WritePin(GPIOD, GPIO_PIN_12, GPIO_PIN_SET);
  HAL_GPIO_WritePin(GPIOD, GPIO_PIN_11, GPIO_PIN_RESET);
  (void)HAL_SPI_Transmit(&hspi1, reinterpret_cast<uint8_t *>(tileBuffer),
                         static_cast<uint16_t>(pixels * 2U), 1000U);
  HAL_GPIO_WritePin(GPIOD, GPIO_PIN_11, GPIO_PIN_SET);
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
void LCD_UpdateAutoBrightness(void) {}
uint16_t LCD_RGB888ToRGB565(uint32_t color) { return boardLCD.rgb888ToRgb565(color); }
uint16_t LCD_GetWidth(void) { return LCD_WIDTH; }
uint16_t LCD_GetHeight(void) { return LCD_HEIGHT; }
uint16_t LCD_GetTileY(void) { return boardLCD.getTileY(); }
uint16_t LCD_GetTileH(void) { return boardLCD.getTileH(); }
}
