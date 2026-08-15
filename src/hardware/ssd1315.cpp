#include "include/ssd1315.hpp"

#include "library/include/liboledgfx.h"

namespace {
constexpr uint32_t kI2cTimeoutMs = 25U;
constexpr uint32_t kFastI2cClockHz = 400000U;

void configureFastI2c(I2C_HandleTypeDef *i2c) {
  if (i2c == nullptr || i2c->Instance == nullptr ||
      i2c->Init.ClockSpeed == kFastI2cClockHz) {
    return;
  }

  i2c->Init.ClockSpeed = kFastI2cClockHz;
  i2c->Init.DutyCycle = I2C_DUTYCYCLE_2;
  (void)HAL_I2C_Init(i2c);
}
}

SSD1315::SSD1315(I2C_HandleTypeDef *i2c, uint8_t address)
    : _i2c(i2c), _address(address), _ready(false), _dmaBusy(false),
      _dmaError(false), _dmaPacket{} {}

bool SSD1315::sendCommands(const uint8_t *commands, std::size_t size) {
  uint8_t packet[32];
  if (_dmaBusy || commands == nullptr || size == 0U || size >= sizeof(packet))
    return false;
  packet[0] = 0x00U;
  for (std::size_t i = 0; i < size; ++i)
    packet[i + 1U] = commands[i];
  return HAL_I2C_Master_Transmit(_i2c, static_cast<uint16_t>(_address << 1U),
                                 packet, static_cast<uint16_t>(size + 1U),
                                 kI2cTimeoutMs) == HAL_OK;
}

bool SSD1315::init() {
  static const uint8_t candidates[] = {0x3CU, 0x3DU};
  static const uint8_t initCommands[] = {
      0xAEU, 0xD5U, 0x80U, 0xA8U, 0x3FU, 0xD3U, 0x00U, 0x40U,
      0x8DU, 0x14U, 0x20U, 0x00U, 0xA1U, 0xC8U, 0xDAU, 0x12U,
      0x81U, 0x7FU, 0xD9U, 0xF1U, 0xDBU, 0x40U, 0xA4U, 0xA6U,
      0x2EU,
  };

  _ready = false;
  configureFastI2c(_i2c);
  for (uint8_t candidate : candidates) {
    if (HAL_I2C_IsDeviceReady(_i2c, static_cast<uint16_t>(candidate << 1U),
                              2U, kI2cTimeoutMs) == HAL_OK) {
      _address = candidate;
      break;
    }
  }
  if (HAL_I2C_IsDeviceReady(_i2c, static_cast<uint16_t>(_address << 1U), 1U,
                            kI2cTimeoutMs) != HAL_OK)
    return false;

  _ready = sendCommands(initCommands, sizeof(initCommands));
  return _ready;
}

bool SSD1315::display(const uint8_t *buffer, std::size_t size) {
  static const uint8_t windowCommands[] = {0x21U, 0x00U, 0x7FU,
                                            0x22U, 0x00U, 0x07U};
  if (!_ready || buffer == nullptr || size != LIBOLEDGFX_BUFFER_SIZE ||
      !sendCommands(windowCommands, sizeof(windowCommands)))
    return false;

  uint8_t packet[129];
  packet[0] = 0x40U;
  for (std::size_t offset = 0U; offset < size; offset += 128U) {
    for (std::size_t i = 0U; i < 128U; ++i)
      packet[i + 1U] = buffer[offset + i];
    if (HAL_I2C_Master_Transmit(_i2c, static_cast<uint16_t>(_address << 1U),
                                packet, sizeof(packet), kI2cTimeoutMs) != HAL_OK)
      return false;
  }
  return true;
}

bool SSD1315::displayPage(uint8_t page, const uint8_t *pageBuffer) {
  if (!_ready || page >= 8U || pageBuffer == nullptr)
    return false;

  const uint8_t windowCommands[] = {0x21U, 0x00U, 0x7FU, 0x22U, page, page};
  if (!sendCommands(windowCommands, sizeof(windowCommands)))
    return false;

  uint8_t packet[129];
  packet[0] = 0x40U;
  for (std::size_t i = 0U; i < 128U; ++i)
    packet[i + 1U] = pageBuffer[i];

  return HAL_I2C_Master_Transmit(_i2c, static_cast<uint16_t>(_address << 1U),
                                 packet, sizeof(packet), kI2cTimeoutMs) ==
         HAL_OK;
}

bool SSD1315::displayPageDma(uint8_t page, const uint8_t *pageBuffer) {
  if (!_ready || _dmaBusy || page >= 8U || pageBuffer == nullptr)
    return false;

  const uint8_t windowCommands[] = {0x21U, 0x00U, 0x7FU, 0x22U, page, page};
  if (!sendCommands(windowCommands, sizeof(windowCommands)))
    return false;

  _dmaPacket[0] = 0x40U;
  for (std::size_t i = 0U; i < 128U; ++i)
    _dmaPacket[i + 1U] = pageBuffer[i];

  _dmaError = false;
  _dmaBusy = true;
  if (HAL_I2C_Master_Transmit_DMA(_i2c, static_cast<uint16_t>(_address << 1U),
                                  _dmaPacket, sizeof(_dmaPacket)) != HAL_OK) {
    _dmaBusy = false;
    return false;
  }
  return true;
}

bool SSD1315::setDisplayOn(bool enabled) {
  if (!_ready || _dmaBusy)
    return false;
  const uint8_t command = enabled ? 0xAFU : 0xAEU;
  return sendCommands(&command, 1U);
}

void SSD1315::onDmaTxComplete(I2C_HandleTypeDef *i2c) {
  if (i2c == _i2c)
    _dmaBusy = false;
}

void SSD1315::onI2cError(I2C_HandleTypeDef *i2c) {
  if (i2c == _i2c) {
    _dmaError = true;
    _dmaBusy = false;
  }
}

SSD1315 oled(&hi2c1);

extern "C" void HAL_I2C_MasterTxCpltCallback(I2C_HandleTypeDef *hi2c) {
  oled.onDmaTxComplete(hi2c);
}

extern "C" void HAL_I2C_ErrorCallback(I2C_HandleTypeDef *hi2c) {
  oled.onI2cError(hi2c);
}
