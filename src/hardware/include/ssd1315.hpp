#ifndef SSD1315_HPP
#define SSD1315_HPP

#include "i2c.h"
#include <cstddef>
#include <cstdint>

class SSD1315 {
public:
  explicit SSD1315(I2C_HandleTypeDef *i2c, uint8_t address = 0x3CU);

  bool init();
  bool display(const uint8_t *buffer, std::size_t size);
  bool setDisplayOn(bool enabled);
  bool ready() const { return _ready; }
  uint8_t address() const { return _address; }

private:
  bool sendCommands(const uint8_t *commands, std::size_t size);

  I2C_HandleTypeDef *_i2c;
  uint8_t _address;
  bool _ready;
};

extern SSD1315 oled;

#endif
